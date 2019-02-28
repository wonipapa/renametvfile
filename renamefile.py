#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from lxml import html
import requests
import urlparse
import json
import re
import os
import sys
import shutil
import errno
from datetime import datetime
import time

reload(sys)
sys.setdefaultencoding('utf8')

DAUM_TV_SRCH = 'https://search.daum.net/search?w=tot&q=%s&rtmaxcoll=TVP'
DAUM_TV_DETAIL = 'https://search.daum.net/search?w=tv&q=%s&irk=%s&irt=tv-program&DA=TVP'
Settingfile = os.path.dirname(os.path.abspath(__file__)) + '/renamefile.json'
JSON_FILE_ERROR = 'json 파일을 읽을 수 없습니다.'
JSON_SYNTAX_ERROR = 'json 파일 형식이 잘못되었습니다.'
VERSION = '0.0.4'
try:
    with open(Settingfile) as f: # Read Channel Information file
        Settings = json.load(f)
        DOWNLOADDIR = Settings['DOWNLOADDIR']
        TARGETDIR   = Settings['TARGETDIR']
        DUPEDIR     = Settings['DUPEDIR']
        IS_GENRE    = Settings['IS_GENRE'] if 'IS_GENRE' in Settings else 'N'
        IS_ETC      = Settings['IS_ETC'] if 'IS_ETC' in Settings else 'Y' 
        IS_SEASON   = Settings['IS_SEASON'] if 'IS_SEASON' in Settings else 'N';
        ZEROFILL    = Settings['ZEROFILL'] if 'ZEROFILL' in Settings else '2'
        DELIMITER   = Settings['DELIMITER'] if 'DELIMITER' in Settings else '.'
except EnvironmentError:
    print("renamefile." + JSON_FILE_ERROR)
    sys.exit()
except ValueError:
    print("renamefile." + JSON_SYNTAX_ERROR)
    sys.exit()

def renamefile(videodir):
    for dirpaths, dirname, files in os.walk((os.path.normpath(videodir).encode('utf-8')), topdown=False):
        for filename in files:
            SourceFile  = os.path.join(dirpaths, filename).decode('utf-8')
            SourceDir   = os.path.dirname(SourceFile)
            videofile     = filename.decode('utf-8')
            episode_title = None
            genre = '미분류'
            episode_number = []
            episode_date = ''
            if os.path.exists(SourceFile.encode('utf-8')):
                fileinfo = re.search('(.*?)(\.E(\d{1,}))?\.((\d{2})(\d{2})(\d{2}))\.(.*)\.(mp4|avi|mkv)', videofile.encode('utf-8'))
                if fileinfo:
                    file_title = fileinfo.group(1)
                    file_title = re.sub(r'[\\/:"*?<>|]+', '', file_title.encode('utf-8')).strip()
                    file_title = re.sub(r'  +', ' ', file_title.encode('utf-8')).strip()
                    match = re.search('(.*) \d{1,}\-\d{1,}회 합본', file_title.encode('utf-8'))
                    if match:
                       file_title = match.group(1)
                    file_number = fileinfo.group(3).lstrip('0') if fileinfo.group(3) else None
                    file_date = fileinfo.group(4)
                    file_year = fileinfo.group(4)
                    file_etc  = fileinfo.group(8)
                    file_ext  = fileinfo.group(9)
                    try:
                        page = requests.get(DAUM_TV_SRCH % (file_title))
                        time.sleep(0.002)
                        tree = html.fromstring(page.content)
                        episode_title = tree.xpath('//div[@id="tvpColl"]//div[@class="head_cont"]//a[@class="tit_info"][last()]')[0].text.strip() if tree.xpath('//div[@id="tvpColl"]//div[@class="head_cont"]//a[@class="tit_info"][last()]') else ''
                        genre = tree.xpath('//div[@class="head_cont"]/div[@class="summary_info"]/span[@class="txt_summary"][1]')[0].text.strip() if tree.xpath('//div[@class="head_cont"]/div[@class="summary_info"]/span[@class="txt_summary"][1]') else '미분류'
                        year = tree.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text if tree.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]') else ''
                        if year is not None:
                            match = re.search('(\d{4})\.\d*\.\d*~?', year.encode('utf-8').strip())
                            if match:
                                try: year = match.group(1)
                                except: year = ''
                        if episode_title is not None:
                            id = urlparse.parse_qs(tree.xpath('//div[@id="tvpColl"]//div[@class="head_cont"]//a[@class="tit_info"][last()]/@href')[0].strip())['irk'][0].strip()
                            try:
                                page = requests.get(DAUM_TV_DETAIL % (episode_title, id))
                                time.sleep(0.003)
                                tree = html.fromstring(page.content)
                                episode_title = re.sub(r'[\\/:"*?<>|]+', '', episode_title.encode('utf-8')).strip()
                                episode_title = re.sub(r'  +', ' ', episode_title.encode('utf-8')).strip()
                                for episodeinfo in tree.xpath('//div[@id="tvpColl"]//ul[@id="clipDateList"]/li') :
                                    try:
                                        episode_date = datetime.strptime(episodeinfo.attrib['data-clip'], '%Y%m%d').strftime('%y%m%d') if episodeinfo.attrib['data-clip'] else ''
                                    except ValueError:
                                        episode_date = ''
                                    if episode_date == file_date:
                                        if episodeinfo.xpath('./a/span[@class="txt_episode"]'):
                                            episode_number.append(episodeinfo.xpath('./a/span[@class="txt_episode"]')[0].text.strip().replace(u'회',''))
                            except: pass
                    except: pass

                    episode_title = file_title if not episode_title else episode_title
                    if len(episode_number):
                        newvideofile = getname(episode_title, episode_number, file_date, file_etc, file_ext)
                    elif file_number:
                        newvideofile = getname(episode_title, file_number, file_date, file_etc, file_ext)
                    else:
                        newvideofile = getname(episode_title, '', file_date, file_etc, file_ext)
                    if IS_GENRE in ['Y', 'y']:
                        if year:
                            episode_title = episode_title + ' (' + year + ')'
                        TargetFile = os.path.join(TARGETDIR, genre, episode_title, newvideofile)
                    else:
                        TargetFile = os.path.join(TARGETDIR, newvideofile)
                    DupeFile = os.path.join(DUPEDIR, newvideofile)
                    if not os.path.exists(TargetFile):
                        try:
                            os.makedirs(os.path.dirname(TargetFile.encode('utf-8')))
                        except OSError as e:
                            if e.errno != errno.EEXIST:
                                raise
                        print('Move %s to %s' %(SourceFile.encode('utf-8'), TargetFile.encode('utf-8')))
                        shutil.move(SourceFile.encode('utf-8'), TargetFile.encode('utf-8'))
                    else:
                        print('Move %s to %s' %(SourceFile.encode('utf-8'), DupeFile.encode('utf-8')))
                        shutil.move(SourceFile.encode('utf-8'), DupeFile.encode('utf-8'))

def getname(title, number, date, etc, ext):
    season_number = 'S01' if IS_SEASON in ['Y', 'y'] else ''
    episode_number = []
    file_etc = etc if IS_ETC in ['Y', 'y'] else None
    file_ext = ext
    if not isinstance(number, list):
       episode_number.append(number)
    elif number:
       episode_number = number
    else:
       episode_number = None
    if any(episode_number):
        season_number = 'S01' if int(episode_number[0]) > 999 else season_number
        episode_number = ['E' + str(item).zfill(2) for item in episode_number]
        episode_number.sort()
        episode_number = season_number + "-".join(episode_number)
    else:
        episode_number = None

    strings = [title, episode_number, date, file_etc]
    newname  = DELIMITER.join(filter(None, strings)) + '.' + file_ext

    return newname
                
renamefile(DOWNLOADDIR)
