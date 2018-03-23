#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from argparse import ArgumentParser
from hashlib import md5
from subprocess import check_output
from subprocess import call
from subprocess import Popen
from time import sleep
from distutils import spawn
from tempfile import NamedTemporaryFile
import json
import random
import re
import sys
import platform

try:
    # Py3
    from urllib.parse import quote, urlencode
    from urllib.request import urlopen
except ImportError:
    # Py 2.7
    from urllib import quote
    from urllib2 import urlopen
    from urllib import urlencode
    reload(sys)
    sys.setdefaultencoding('utf8')

class GlobalOptions(object):
    def __init__(self, options=None):
        self._options = options

    def __getattr__(self, name):
        if name in dir(GlobalOptions) or name in self.__dict__:
            return getattr(self, name)
        elif name in self._options.__dict__:
            return getattr(self._options, name)
        else:
            raise AttributeError("'%s' has no attribute '%s'" % (
                self.__class__.__name__, name))

options = GlobalOptions()


class Colorizing(object):
    colors = {
        'none': "",
        'default': "\033[0m",
        'bold': "\033[1m",
        'underline': "\033[4m",
        'blink': "\033[5m",
        'reverse': "\033[7m",
        'concealed': "\033[8m",

        'black': "\033[30m",
        'red': "\033[31m",
        'green': "\033[32m",
        'yellow': "\033[33m",
        'blue': "\033[34m",
        'magenta': "\033[35m",
        'cyan': "\033[36m",
        'white': "\033[37m",

        'on_black': "\033[40m",
        'on_red': "\033[41m",
        'on_green': "\033[42m",
        'on_yellow': "\033[43m",
        'on_blue': "\033[44m",
        'on_magenta': "\033[45m",
        'on_cyan': "\033[46m",
        'on_white': "\033[47m",

        'beep': "\007",
    }

    @classmethod
    def colorize(cls, s, color=None):
        if options.color == 'never':
            return s
        if options.color == 'auto' and not sys.stdout.isatty():
            return s
        if color in cls.colors:
            return "{0}{1}{2}".format(
                cls.colors[color], s, cls.colors['default'])
        else:
            return s


def online_resources(query):

    english = re.compile('^[a-z]+$', re.IGNORECASE)
    chinese = re.compile('^[\u4e00-\u9fff]+$', re.UNICODE)

    res_list = [
        (english, 'http://www.ldoceonline.com/search/?q={0}'),
        (english, 'http://dictionary.reference.com/browse/{0}'),
        (english, 'http://www.urbandictionary.com/define.php?term={0}'),
        (chinese, 'http://www.zdic.net/sousuo/?q={0}')
    ]

    return [url.format(quote(query.encode('utf-8')))
            for lang, url in res_list if lang.match(query) is not None]


def print_explanation(data, options):
    _c = Colorizing.colorize
    _d = data
    has_result = False
    _accent_urls = dict()

    query = _d['query']
    print(_c(query, 'underline'), end='')

    if 'basic' in _d:
        has_result = True
        _b = _d['basic']

        try:
            if 'uk-phonetic' in _b and 'us-phonetic' in _b:
                print(" UK: [{0}]".format(_c(_b['uk-phonetic'], 'yellow')), end=',')
                print(" US: [{0}]".format(_c(_b['us-phonetic'], 'yellow')))
            elif 'phonetic' in _b:
                print(" [{0}]".format(_c(_b['phonetic'], 'yellow')))
            else:
                print()
        except UnicodeEncodeError:
            print(" [ ---- ] ")

        if options.speech and 'speech' in _b:
            print(_c('  Text to Speech:', 'cyan'))
            if 'us-speech' in _b and 'uk-speech' in _b:
                print("     * UK:", _b['uk-speech'])
                print("     * US:", _b['us-speech'])
            elif 'speech' in _b:
                print("     *", _b['speech'])
            for _accent in ('speech', 'uk-speech', 'us-speech'):
                if _accent in _b:
                    _accent_urls.update({_accent.split('-')[0]: _b[_accent]})
            print()

        if 'explains' in _b:
            print(_c('  Word Explanation:', 'cyan'))
            print(*map("     * {0}".format, _b['explains']), sep='\n')
        else:
            print()
    elif 'translation' in _d:
        has_result = True
        print(_c('\n  Translation:', 'cyan'))
        print(*map("     * {0}".format, _d['translation']), sep='\n')
    else:
        print()

    if options.simple is False:
        # Web reference
        if 'web' in _d:
            has_result = True
            print(_c('\n  Web Reference:', 'cyan'))

            web = _d['web'] if options.full else _d['web'][:3]
            print(*[
                '     * {0}\n       {1}'.format(
                    _c(ref['key'], 'yellow'),
                    '; '.join(map(_c('{0}', 'magenta').format, ref['value']))
                ) for ref in web], sep='\n')

        # Online resources
        ol_res = online_resources(query)
        if len(ol_res) > 0:
            print(_c('\n  Online Resource:', 'cyan'))
            res = ol_res if options.full else ol_res[:1]
            print(*map(('     * ' + _c('{0}', 'underline')).format, res), sep='\n')

        # read out the word
        if options.read:
            print()
            sys_name = platform.system()
            if 'Darwin' == sys_name:
                call(['say', query])
            elif 'Linux' == sys_name:
                if not spawn.find_executable(options.player):
                    print(_c(' -- Player ' + options.player + ' is not found in system, ', 'red'))
                    print(_c('    acceptable players are: festival, mpg123, sox and mpv', 'red'))
                    print(_c(' -- Please install your favourite player: ', 'blue'))
                    print(_c('    - festival (http://www.cstr.ed.ac.uk/projects/festival/),'))
                    print(_c('    - mpg123 (http://www.mpg123.de/),'))
                    print(_c('    - SoX (http://sox.sourceforge.net/),'))
                    print(_c('    - mpv (https://mpv.io).'))
                else:
                    if options.player == 'festival':
                        Popen('echo ' + query + ' | festival --tts', shell=True)
                    else:
                        accent = options.accent if options.accent != 'auto' else 'speech'
                        accent_url = _accent_urls.get(accent, '')
                        if not accent_url:
                            print(_c(' -- URL to speech audio for accent {} not found.'.format(options.accent), 'red'))
                            if not options.speech:
                                print(_c(' -- Maybe you forgot to add -S option?'), 'red')
                        else:
                            with NamedTemporaryFile(suffix=".mp3") as accent_file:
                                if call('curl -s "{0}" -o {1}'.format(accent_url, accent_file.name), shell=True) != 0:
                                    print(_c('Network unavailable or permission error to write file: {}'.format(accent_file), 'red'))
                                else:
                                    if options.player == 'mpg123':
                                        call('mpg123 -q ' + accent_file.name, shell=True)
                                    elif options.player == 'sox':
                                        call('play -q ' + accent_file.name, shell=True)
                                    elif options.player == 'mpv':
                                        call('mpv --really-quiet ' + accent_file.name, shell=True)

    if not has_result:
        print(_c(' -- No result for this query.', 'red'))

    print()


def lookup_word(unquted_word):
    word = quote(unquted_word)
    if word == '%5Cq' or word == '%3Aq':
        print("Thanks for using, goodbye!")
        sys.exit()

    try:
        params = {
            'q': word,
            'from': 'EN',
            'to': 'zh-CHS',
            'appKey': options.appid,
            'salt': random.randint(1, 65535),
        }
        params['sign'] = md5(
            '{app_id}{q}{salt}{app_key}'.format(
                app_id=options.appid, q=unquted_word, salt=params['salt'], app_key=options.appkey).encode('utf-8')
        ).hexdigest()

        query = urlencode(params)

        resp = urlopen('http://openapi.youdao.com/api?%s' % query)

    except IOError as err:
        print(err)
    else:

        json_data = json.loads(resp.read().decode('utf-8'))
        err_code = json_data.get('errorCode')
        if err_code == '0':
            print_explanation(json_data, options)
        else:
            err_code_reason = '''
            101 缺少必填的参数，出现这个情况还可能是et的值和实际加密方式不对应
            102 不支持的语言类型
            103 翻译文本过长
            104 不支持的API类型
            105 不支持的签名类型
            106 不支持的响应类型
            107 不支持的传输加密类型
            108 appKey无效，注册账号， 登录后台创建应用和实例并完成绑定， 可获得应用ID和密钥等信息，其中应用ID就是appKey（ 注意不是应用密钥）
            109 batchLog格式不正确
            110 无相关服务的有效实例
            111 开发者账号无效，可能是账号为欠费状态
            201 解密失败，可能为DES,BASE64,URLDecode的错误
            202 签名检验失败
            203 访问IP地址不在可访问IP列表
            301 辞典查询失败
            302 翻译查询失败
            303 服务端的其它异常
            401 账户已经欠费停
            '''
            code_explain_list = [line.strip().split(' ', 1) for line in err_code_reason.split('\n') if line.strip()]
            code_explain_dict = dict(code_explain_list)
            print(code_explain_dict.get(err_code, '未知错误'))


def arg_parse():
    parser = ArgumentParser(description="Youdao Console Version")
    parser.add_argument('-i', '--appid', required=True, help='Application ID')
    parser.add_argument('-k', '--appkey', required=True, help='Application Secret')
    parser.add_argument('-f', '--full',
                        action="store_true",
                        default=False,
                        help="print full web reference, only the first 3 "
                             "results will be printed without this flag.")
    parser.add_argument('-s', '--simple',
                        action="store_true",
                        default=False,
                        help="only show explainations. "
                             "argument \"-f\" will not take effect.")
    parser.add_argument('-S', '--speech',
                        action="store_true",
                        default=False,
                        help="print URL to speech audio.")
    parser.add_argument('-r', '--read',
                        action="store_true",
                        default=False,
                        help="read out the word with player provided by \"-p\" option.")
    parser.add_argument('-p', '--player',
                        choices=['festival', 'mpg123', 'sox', 'mpv'],
                        default='festival',
                        help="read out the word with this play."
                             "Default to 'festival' or can be 'mpg123', 'sox', 'mpv'."
                             "-S option is required if player is not festival."
                        )
    parser.add_argument('-a', '--accent',
                        choices=['auto', 'uk', 'us'],
                        default='auto',
                        help="set default accent to read the word in. "
                             "Default to 'auto' or can be 'uk', or 'us'."
                        )
    parser.add_argument('-x', '--selection',
                        action="store_true",
                        default=False,
                        help="show explaination of current selection.")
    parser.add_argument('--color',
                        choices=['always', 'auto', 'never'],
                        default='auto',
                        help="colorize the output. "
                             "Default to 'auto' or can be 'never' or 'always'.")
    parser.add_argument('words',
                        nargs='*',
                        help="words to lookup, or quoted sentences to translate.")
    return parser.parse_args()


def main():
    options._options = arg_parse()

    if options.words:
        for word in options.words:
            lookup_word(word)
    else:
        if options.selection:
            last = check_output(["xclip", "-o"], universal_newlines=True)
            while True:
                try:
                    sleep(0.1)
                    curr = check_output(["xclip", "-o"], universal_newlines=True)
                    if curr != last:
                        last = curr
                        if last.strip():
                            lookup_word(last)
                        print("Waiting for selection>")
                except (KeyboardInterrupt, EOFError):
                    break
        else:
            try:
                import readline
            except ImportError:
                pass
            while True:
                try:
                    if sys.version_info[0] == 3:
                        words = input('> ')
                    else:
                        words = raw_input('> ')
                    if words.strip():
                        lookup_word(words)
                except KeyboardInterrupt:
                    print()
                    continue
                except EOFError:
                    break
        print("\nBye")

if __name__ == "__main__":
    main()
