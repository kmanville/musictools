#!/usr/bin/env python

import os
import re
import shutil
import taglib
import argparse
from pprint import pprint
from titlecase import titlecase
from easydict import EasyDict as edict

parser = argparse.ArgumentParser()
parser.add_argument('albums', type=str, nargs='+')
parser.add_argument('-o', '--output', type=str)
parser.add_argument('-m', '--modify_tag', type=str, nargs='+')
parser.add_argument('-r', '--remove_tag', type=str, nargs='+')
parser.add_argument('-i', '--info', action='store_true')
parser.add_argument('-c', '--clean', action='store_true')
args = parser.parse_args()

mustypes = set(['.mp3','.flac','.ogg'])
exttypes = set(['.jpg','.jpeg','.png','.tif','.tiff', '.log', '.cue'])
pattern = os.path.join('%genre%', '%artist%| [%country%]|', '%type%', '%date% %album%| [%issue%]|', '|%discnumber%|%tracknumber% %title%| [%source%]|')

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if os.path.isdir(path):
            pass
        else: raise


#print all tags
def _info(path):
    expected = set({'ALBUM', 'ARTIST', 'COUNTRY', 'DATE', 'TRACKNUMBER', 'DISCNUMBER', 'GENRE', 'TITLE', 'TYPE', 'ISSUE'})
    _, ext = os.path.splitext(path)
    print path
    if ext.lower() in mustypes:
        f = taglib.File(path)
        missing = expected - set(f.tags.keys())
        if len(missing):
            print 'missing:', missing
        pprint(f.tags, indent=4)


def info(path):
    if os.path.isfile(path):
        _info(path)
    else:
        for dir, dirnames, filenames in os.walk(path):
            for filename in filenames:
                _info(os.path.join(dir, filename))


#remove all tags that are not specified in pattern
#zero pad tracknumber
def clean(ipath):
    for dir,dirnames,filenames in os.walk(ipath):
        for filename in filenames:
            _,ext=os.path.splitext(filename)
            if ext.lower() in mustypes:
                src = os.path.join(dir, filename)

                f = taglib.File(src)

                if 'TRACKNUMBER' not in f.tags.keys():
                    number = re.match('(\d*).*', filename)
                    if not number:
                        continue
                    number = int(number.group(1))
                    number = number - 100 if number > 100 else number
                    f.tags['TRACKNUMBER'] = str(number)

                #zero pad track number
                if 'TRACKNUMBER' in f.tags.keys():
                    tracknumber = f.tags['TRACKNUMBER'][0]
                    tracknumber = re.match('(\d*).*', tracknumber).group(1)
                    del f.tags['TRACKNUMBER']
                    f.tags['TRACKNUMBER'] = tracknumber.zfill(2)

            
                if 'DISCNUMBER' in f.tags.keys():
                    discnumber = f.tags['DISCNUMBER'][0]
                    discnumber = re.match('(\d*).*', discnumber).group(1)
                    del f.tags['DISCNUMBER']
                    f.tags['DISCNUMBER'] = discnumber
                else:
                    f.tags['DISCNUMBER'] = '1'

                #cleanup issue
                if 'ISSUE' in f.tags.keys():
                    issue = f.tags['ISSUE'][0]
                    issue = re.split(', |,', issue)
                    if len(issue) > 1:
                        issue = ', '.join(issue[1::2])
                    else:
                        issue=issue[0]
                    if issue=='Self Released':
                        issue = 'SELF'
                    elif issue=='Bootleg':
                        issue = 'BOOT'
                    del f.tags['ISSUE']
                    f.tags['ISSUE'] = issue.upper()

                #delete extra tags
                todelete=[]
                for tag, value in f.tags.iteritems():
                    if tag.lower() not in pattern:
                        todelete.append(tag)
                for td in todelete:
                    del f.tags[td]

                #title case
                title = titlecase(f.tags['TITLE'][0])
                del f.tags['TITLE']
                f.tags['TITLE'] = title
                album = titlecase(f.tags['ALBUM'][0])
                del f.tags['ALBUM']
                f.tags['ALBUM'] = album
                artist = titlecase(f.tags['ARTIST'][0])
                del f.tags['ARTIST']
                f.tags['ARTIST'] = artist

                if 'TYPE' in f.tags.keys():
                    type = f.tags['TYPE'][0].lower()
                    del f.tags['TYPE']
                    f.tags['TYPE'] = type

                f.save()


#modify list of tags in mod
#remove list of tags in rem
def _tag(path, mod, rem):
    _, ext = os.path.splitext(path)
    if ext.lower() in mustypes:
        f = taglib.File(path)
        if mod is not None:
            for m in mod:
                k, v = m.split('=')
                #del f.tags[k]
                f.tags[k.upper()] = [unicode(v,'utf-8')]
        if rem is not None:
            for r in rem:
                del f.tags[r.upper()]
        f.save()



def tag(ipath, mod, rem):
    if os.path.isfile(ipath):
        _tag(ipath, mod, rem)
    else:
        for dir, dirnames, filenames in os.walk(ipath):
            for filename in filenames:
                _tag(os.path.join(dir, filename), mod, rem)


#rename files from tags to pattern
def tag2file(ipath, opath):
    tomove = []
    extra = []
    for dir, dirnames, filenames in os.walk(ipath):
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext.lower() in mustypes:
                src = os.path.join(dir, filename)
                dst = pattern

                f = taglib.File(src)
                for tag, value in f.tags.iteritems():
                    value = [v.replace('/', '-') for v in value]
                    dst = dst.replace('%'+tag.lower()+'%',', '.join(value))
                dst = re.sub(r'\|[^\|]*%[a-z]+%[^|]*\|','',dst) #remove optional tags that were not supplied
                dst = re.sub(r'\|([^\|]*)\|','\\1',dst)         #remove optional markers
                dst = os.path.join(opath, dst + ext)
                tomove.append((src,dst))
            elif ext.lower() in exttypes:
                src = os.path.join(dir, filename)
                extra.append(src)


    #clean up src directory
    for dir, dirnames, filenames in os.walk(ipath):
        if os.listdir(dir) == []:
            print 'removing {}'.format(dir)
            os.rmdir(dir)
        

    if len(tomove) == 0:
        return

    #make sure we are dealing with a single album
    dsts = set()
    for src, dst in tomove:
        dsts.add(os.path.dirname(dst))
    if len(dsts) != 1:
        print 'more than one destination, cleanup tags first'
        print dsts
        return

    #move music files
    dest = dsts.pop()
    mkdir_p(dest)
    print 'moving files to {}'.format(dest)

    for src, dst in tomove:
        if src == dst: continue
        shutil.move(src, dst)

    #move extra files
    for src in extra:
        _, ext = os.path.splitext(src)
        if ext == '.log' or ext == '.cue':
            file = 'rip'+ext
        else:
            file = os.path.basename(src)
        dst = os.path.join(dest, file)
        if src == dst:
            continue

        i = 1
        while os.path.exists(dst):
            dst = str(i).join(os.path.splitext(dst))
        i = i + 1

        shutil.move(src, dst)

    #clean up src directory
    for dir, dirnames, filenames in os.walk(ipath):
        if os.listdir(dir) == []:
            print 'removing {}'.format(dir)
            os.rmdir(dir)
        


if args.info:
    for album in args.albums:
        info(album)
if args.clean:
    for album in args.albums:
        clean(album)
if (args.modify_tag and len(args.modify_tag) > 0) or (args.remove_tag and len(args.remove_tag) > 0):
    for album in args.albums:
        tag(album, args.modify_tag, args.remove_tag);
if args.output:
    for album in args.albums:
        tag2file(album, args.output)
