import requests
from requests.exceptions import RequestException
import time
import re
import json
from bs4 import BeautifulSoup
import pymongo
from hashlib import md5
import os
from multiprocessing import Pool
'''
关键词：Ajax，mongodb,多进程，图片下载
优化：添加更多的判断
'''


'''
mongodb配置
'''
mongo_url='localhost'
mondo_db='toutiao'
mondo_table='jiepai'

#创建数据库对象
#不加connect=False会因为多进程而且报错
client=pymongo.MongoClient(mongo_url,connect=False)
db=client[mondo_db]

KeyWord='街拍'

#索引页面请求 得到组图页面 get传参 Ajax请求
def get_index_page(page,keyword):
    data={
        'offset': page,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': 20,
        'cur_tab': 3,
        'from':'gallery'
    }
    url='https://www.toutiao.com/search_content/'
    try:
        res=requests.get(url,params=data)
        res.encoding=res.apparent_encoding
        if res.status_code==200:
            return res.text
        return None
    except RequestException:
        print('请求索引页面出错')
        return None
#解析索引页面 得到详情页的url
def parser_index_page(content):
    # content是一个json字符串 这里把他转换成真正的字典格式
    data=json.loads(content)
    if 'data' in data.keys():
        for item in data['data']:
            #生成器
            yield item['article_url']
            #这里的item还是一个字典
            # print(item['article_url'],item['title'],end='\n')
#详情页请求
def get_datail_page(url):
    try:
        res = requests.get(url)
        res.encoding = res.apparent_encoding
        if res.status_code == 200:
            return res.text
        return None
    except RequestException:
        print('请求详情页面出错：',url)
        return None
#详情页解析
def parser_datail_page(html,url):
    soup=BeautifulSoup(html,'lxml')
    title=soup.select('title')[0].get_text()
    images_pattern=re.compile(r'gallery: JSON.parse\("(.*?)"\)',re.S)
    every_group=re.search(images_pattern,html)
    if every_group:
        # print(type(every_group.group(1)),'\n')
        #这里有个神奇 的干扰选项  ’\‘ 有干扰 先剔除
        result=json.loads(every_group.group(1).replace('\\',''))
        if 'sub_images' in result:
            sub_images=result['sub_images']
            #在sub_images'键里得到所有的url
            imag_url=[item['url'] for item in sub_images]

            #这里开始下载图片到本地
            for img in imag_url:
                downloads_images(img)
            #返回一个字典存储到mongo
            return {
                'title':title,
                'url':url,
                'images':imag_url
            }
#保存到数据库
def save_mongo(content):
    if db[mondo_table].insert(content):
        print('储存到Mongo成功！')
        return True
    else:
        print("数据存储失败")
        return None

def downloads_images(image_url):
    print('正在下载：',image_url)
    try:
        res=requests.get(image_url)
        res.encoding=res.apparent_encoding
        if res.status_code==200:
            #调用save_images函数
            save_images(res.content)
        return None
    except RequestException:
        print('请求图片出错')
        return None
def save_images(content_images):
    #创建图片保存路径和名称 理由md5编码作为图片名称
    image_path='{0}/{1}.{2}'.format('/home/yuchou/jiepai',md5(content_images).hexdigest(),'jpg')
    if not os.path.exists(image_path):
        with open(image_path,'wb') as f:
            f.write(content_images)
            f.close()



def main(page):
    #自己定义一个阈值
    html=get_index_page(page,KeyWord)
#  得到所有的url
    for item in parser_index_page(html):
        detail_html=get_datail_page(item)
        if detail_html:
            #返回的额是一个字典
            results=parser_datail_page(detail_html,item)
            if results:
                save_mongo(results)


if __name__=='__main__':
    pages = int(input('请输入爬取的最大值：（大于等于0的整数）'))
    #开启多线程
    pool=Pool()
    page_list=[i*20 for i in range(0,pages)]
    start_time=time.time()
    pool.map(main,page_list)
    print(time.time()-start_time)
    print('爬取存储完毕！')