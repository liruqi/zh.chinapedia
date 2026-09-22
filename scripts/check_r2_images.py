#!/usr/bin/env python3
"""批量检查 docs 里所有 R2 图片的尺寸，标记超高图。

用法:
    python scripts/check_r2_images.py
    python scripts/check_r2_images.py --limit 50
    python scripts/check_r2_images.py --tall-only   # 只显示 ratio>1.0 的

输出字段：文件名、宽×高、宽高比、所在文件、是否超高。
"""
import argparse
import os
import re
import sys
import urllib.request


def read_size(data):
    """从图片前 200KB 里读取宽高。支持 PNG/JPEG/GIF。"""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        w = int.from_bytes(data[16:20], 'big')
        h = int.from_bytes(data[20:24], 'big')
        return w, h
    if data[:2] == b'\xff\xd8':
        j = 2
        while j < len(data):
            if data[j] != 0xff:
                break
            marker = data[j + 1]
            if marker in (0xc0, 0xc1, 0xc2):
                h = int.from_bytes(data[j + 5:j + 7], 'big')
                w = int.from_bytes(data[j + 7:j + 9], 'big')
                return w, h
            if marker == 0xd9:
                break
            length = int.from_bytes(data[j + 2:j + 4], 'big')
            j += 2 + length
        return None, None
    if data[:4] == b'GIF8':
        w = int.from_bytes(data[6:8], 'little')
        h = int.from_bytes(data[8:10], 'little')
        return w, h
    return None, None


def collect_images(docs_dir):
    """扫描 docs 下所有 .md，收集不重复的 R2 图片 URL。"""
    pat = re.compile(r'https://pub-[^\s)"\']+\.r2\.dev/[^\s)"\']+')
    seen = set()
    out = []
    for root, _dirs, files in os.walk(docs_dir):
        for f in files:
            if not f.endswith('.md'):
                continue
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as fh:
                text = fh.read()
            for m in pat.finditer(text):
                url = m.group(0)
                if url not in seen:
                    seen.add(url)
                    out.append((path, url))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--docs', default='docs', help='docs 目录路径')
    ap.add_argument('--limit', type=int, default=0, help='最多检查 N 张（0=全部）')
    ap.add_argument('--tall-only', action='store_true', help='只显示竖版/超高图')
    args = ap.parse_args()

    items = collect_images(args.docs)
    total = len(items)
    print('发现 %d 张不重复的 R2 图片' % total, file=sys.stderr)

    if args.limit and args.limit < total:
        items = items[:args.limit]
        print('本次只检查前 %d 张' % args.limit, file=sys.stderr)

    UA = 'Mozilla/5.0'
    checked = 0
    tall = 0
    super_tall = 0

    for path, url in items:
        fname = url.split('/')[-1]
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            data = urllib.request.urlopen(req, timeout=20).read(200000)
            w, h = read_size(data)
            if w and h:
                ratio = h / w
                flag = ''
                if ratio > 1.5:
                    flag = 'SUPER_TALL'
                    super_tall += 1
                elif ratio > 1.0:
                    flag = 'TALL'
                    tall += 1
                if args.tall_only and ratio <= 1.0:
                    continue
                checked += 1
                print('%s\t%d\t%d\t%.2f\t%s\t%s' % (
                    fname, w, h, ratio, flag, os.path.relpath(path, args.docs)))
            else:
                checked += 1
                print('%s\t?\t?\t?\tUNKNOWN_FORMAT\t%s' % (
                    fname, os.path.relpath(path, args.docs)))
        except Exception as e:
            checked += 1
            print('%s\t?\t?\t?\tERROR:%s\t%s' % (
                fname, e, os.path.relpath(path, args.docs)))

    print('检查完成：%d 张，TALL=%d，SUPER_TALL=%d' % (checked, tall, super_tall),
          file=sys.stderr)


if __name__ == '__main__':
    main()
