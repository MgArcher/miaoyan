"""
!/usr/bin/env python
-*- coding: utf-8 -*-
@Time    : 2019/1/9 14:51
@Author  : jiajia
@File    : maoyan.py
"""
import re
import json
import base64
import requests
from urllib.parse import urlencode

import pymongo
from pyquery import PyQuery as pq
from fontTools.ttLib import TTFont

from TheUserAgent import UserAgent
ua = UserAgent()


class MaoYan(object):
    def __init__(self):
        self.req = requests.Session()
        self.start_url = 'https://piaofang.maoyan.com/dayoffice?'
        self.start_referer = 'https://piaofang.maoyan.com/?'
        self.url = 'https://piaofang.maoyan.com/?ver=normal'
        self.header = {
            'user-agent': ua.random_userAgent()
        }
        self.date_time = None
        self.min_year = 2018
        self.max_year = 2018

    def detect(self, s):
        """
        get file encoding or bytes charset
        获取文件字符编码
        :param s: file path or bytes data

        :return: encoding charset
        """
        # info: UTF includes ISO8859-1，GB18030 includes GBK，GBK includes GB2312，GB2312 includes ASCII
        CODES = ['GB18030', 'UTF-8', 'UTF-16', 'BIG5']
        # UTF-8 BOM prefix
        UTF_8_BOM = b'\xef\xbb\xbf'
        if type(s) == str:
            with open(s, 'rb') as f:
                data = f.read()
        elif type(s) == bytes:
            data = s
        else:
            raise TypeError('unsupported argument type!')

        # iterator charset
        for code in CODES:
            try:
                data.decode(encoding=code)
                if 'UTF-8' == code and data.startswith(UTF_8_BOM):
                    return 'UTF-8-SIG'
                return code
            except UnicodeDecodeError:
                continue
        raise Exception("unknown charset!")

    def get_request(self, url, header=None):
        while True:
            try:
                if header is None:
                    header = dict()
                    header['user-agent'] = ua.random_userAgent()
                else:
                    header = header
                response = self.req.get(url, headers=header, timeout=3)
            except:
                continue
            if response.status_code == 200:
                break
            else:
                continue
        response = response.content
        # detect继承自父类
        coding = self.detect(response)
        response = response.decode(coding)
        return response

    # 创建一个日期生成器每次访问生成一个日期 从2018-01-01开始到2018-12-31
    def get_date(self):
        for year in range(self.min_year, self.max_year + 1):
            for month in range(1, 12 + 1):
                if month in [4, 6, 9, 11]:
                    max_day = 30
                else:
                    max_day = 31
                if month == 2:
                    if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:
                        max_day = 29
                    else:
                        max_day = 28
                for day in range(1, max_day + 1):
                    date = "%d-%02d-%02d" % (year, month, day)
                    yield date

    def get_html(self):
        response = self.get_request(self.url, self.header)
        data = json.loads(response)
        for item in self.parse_html(data):
            yield item

    def parse_html(self, data):
        text = data['ticketList']
        html = pq(text)
        for item in html('.canTouch').items():
            item_dict = {
                'name': item('.c1 b').text(),
                'time': self.date_time,
                # 累积票房
                'ljpf': item('.c1 em:nth-child(4)').text(),
                #上映时间
                'sysj': item('.solid em').text(),
                'sspf': item('.c2 b').text(),
                'pfzb': item('.c3').text(),
                'ppzb': item('.c4').text(),
                'szl': item('.c5 span').text(),
                'url': re.findall("href:'(.*)'\">", str(item))[0]
            }
            yield item_dict

    def run(self):
        response = self.get_request(self.url, self.header)
        uid = re.findall('<meta name="csrf" content="(.*?)" />', response)[0]
        for date in self.get_date():
            params = {
                'date': date,
                'cnt': 10,
            }
            self.url = self.start_url + urlencode(params)
            self.header['referer'] = self.start_referer + urlencode({'date': date})
            self.header['uid'] = uid
            self.header['X-Requested-With'] = "XMLHttpRequest"
            self.date_time = date
            for item in self.get_html():
                yield item


class Movie(MaoYan):
    def __init__(self):
        super(Movie, self).__init__()
        self.movie_url_start = "https://piaofang.maoyan.com"
        self.movie_url = ""
        self.font = []
        self.font_b = []
        self.font_file = r"testotf2.woff"
        self.font_file_b = r"testotf2old.woff"
        self.open_spider()

    def open_spider(self):
        self.client = pymongo.MongoClient(
            host='localhost',
            port=27017
        )
        self.db = self.client['jiajia']
        self.collection = self.db['maoyan2018']

    # 加载本地字体文件
    def mist(self):
        # 将本地的woff文件的字形排序得到一个保存有字形的列表
        font = TTFont(self.font_file_b)  # 打开文件
        uniList = font['cmap'].tables[0].ttFont.getGlyphOrder()  # 取出字形保存到uniList中
        # 索引为0和1不是数字
        self.font_b.append(font['glyf'][uniList[7]])  # 0的字形在该uniList所在索引为7
        self.font_b.append(font['glyf'][uniList[10]])  # 1的字形在该uniList所在索引为10
        self.font_b.append(font['glyf'][uniList[5]])
        self.font_b.append(font['glyf'][uniList[6]])
        self.font_b.append(font['glyf'][uniList[9]])
        self.font_b.append(font['glyf'][uniList[2]])
        self.font_b.append(font['glyf'][uniList[11]])
        self.font_b.append(font['glyf'][uniList[3]])
        self.font_b.append(font['glyf'][uniList[4]])
        self.font_b.append(font['glyf'][uniList[8]])

    # 获得字体加密库，按顺序存入list中
    def get_ziku(self, data):
        self.font = []

        def find_num(font, num):
            # num表示要排序的字形位置,font表示打开的woff文件
            uniList_new = font['cmap'].tables[0].ttFont.getGlyphOrder()  # 取出没有排序文件的字形保存到uniList中
            st = font['glyf'][uniList_new[num]]  # 找到要排序字形
            if st in self.font_b:
                return self.font_b.index(st)  # 返回该字形对应的数字

        data = re.findall('<style id="js-nuwa">([\s\S]*?)</style>', data)[0]
        try:
            base64_string = data.split('base64,')[1].split(')')[0]
            bin_data = base64.decodebytes(base64_string.encode())
        except IndexError:
            try:
                ax = re.findall('url\((.*?.woff)\)', data)[0]
                url = 'http:' + ax
                bin_data = requests.get(url).content
            except IndexError:
                print('未寻找到加密')

        with open(self.font_file, 'wb')as f:
            f.write(bin_data)
        # 打开字体文件，创建 self.font属性
        Font = TTFont(self.font_file)
        gly_list_x = Font.getGlyphOrder()

        # 枚举, number是下标，用于找到字形,gly是乱码
        gly_list = [0 for i in range(10)]
        for number, gly in enumerate(gly_list_x):
            x = str(find_num(Font, number))
            if x != 'None':
                gly_list[int(x)] = gly
        for i in gly_list:
            i = i.replace('uni', 'u').lower()
            self.font.append(i.encode('unicode_escape'))

    # 破解字库加密, 对加密文字进行替换
    def decryption(self, data):
        new_data = []
        for s in data:
            b = s.encode('unicode_escape')
            b = b[1:]
            if b in self.font:
                b = self.font.index(b)
                new_data.append(str(b))
            else:
                new_data.append(s)
        data = ''.join(new_data)
        return data

    def get_movie_html(self):
        headers = {
            'referer': self.header['referer'],
            'user-agent': ua.random_userAgent()
        }
        response = self.get_request(self.movie_url, header=headers)
        self.get_ziku(response)
        html = pq(response)
        data = []
        for item in html('.topboard-detail').items():
            data.append([item('.topboard-name-text').text(), self.decryption(item('.topboard-num').text())])
        if len(data) != 2:
            for _ in range(len(data), 2):
                data.append(['空', '空'])
        data.append(html('.rating-num').text() if html('.rating-num').text() else '空')
        return data

    def save_mongo(self, item):
        self.collection.insert(item)

    def main(self):
        self.mist()
        # 继承父类的run函数
        for item in self.run():
            self.movie_url = self.movie_url_start + item['url']
            data = self.get_movie_html()
            item['cspf'] = data[0]
            item['ytpf'] = data[1]
            item['pf'] = data[2]
            # self.save_mongo(item)
            print(item)


if __name__ == '__main__':
    movie = Movie()
    movie.main()
