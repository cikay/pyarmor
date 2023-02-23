#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
#############################################################
#                                                           #
#      Copyright @ 2023 -  Dashingsoft corp.                #
#      All rights reserved.                                 #
#                                                           #
#      Pyarmor                                              #
#                                                           #
#      Version: 8.0.1 -                                     #
#                                                           #
#############################################################
#
#
#  @File: cli/main.py
#
#  @Author: Jondy Zhao (pyarmor@163.com)
#
#  @Create Date: Thu Jan 12 10:27:05 CST 2023
#
import argparse
import logging
import os
import sys

from .errors import CliError
from .context import Context
from .register import LocalRegister, RealRegister
from .config import Configer
from .shell import PyarmorShell

logger = logging.getLogger('Pyarmor')


def _cmd_gen_key(builder, options):
    n = len(options['inputs'])
    if n > 2:
        raise CliError('too many args %s' % options['inputs'][1:])

    keyname = builder.ctx.runtime_keyid if n == 1 else options['inputs'][1]

    logger.info('start to generate outer runtime key "%s"', keyname)
    data = builder.generate_runtime_key(outer=keyname)
    output = options.get('output', 'dist')
    os.makedirs(output, exist_ok=True)

    target = os.path.join(output, keyname)
    logger.info('write %s', target)
    with open(target, 'wb') as f:
        f.write(data)
    logger.info('generate outer runtime key OK')


def _cmd_gen_runtime(builder, options):
    if len(options['inputs']) > 1:
        raise CliError('too many args %s' % options['inputs'][1:])

    output = options.get('output', 'dist')

    logger.info('start to generate runtime package')
    builder.generate_runtime(output)

    keyname = os.path.join(output, builder.ctx.runtime_keyfile)
    logger.info('write "%s"', keyname)
    with open(keyname, 'wb') as f:
        f.write(builder.ctx.runtime_key)
    logger.info('generate runtime package to "%s" OK', output)


def format_gen_args(ctx, args):
    options = {}
    for x in ('recursive', 'findall', 'inputs', 'output', 'no_runtime',
              'enable_bcc', 'enable_jit', 'enable_rft', 'enable_themida',
              'obj_module', 'obf_code', 'assert_import', 'assert_call',
              'mix_name', 'mix_str', 'relative_import', 'restrict_module',
              'platforms', 'outer', 'period', 'expired', 'devices'):
        v = getattr(args, x)
        if v is not None:
            options[x] = v

    restrict = options.get('restrict_module', 0)
    if restrict > 1:
        options['mix_name'] = 1

    if args.enables:
        for x in args.enables:
            options['enable_' + x] = True

    if args.relative:
        options['relative_import'] = args.relative

    if args.no_wrap:
        options['wrap_mode'] = 0

    if args.includes:
        options['includes'] = ' '.join(args.includes)
    if args.excludes:
        options['excludes'] = ' '.join(args.excludes)

    return options


def check_gen_context(ctx):
    if ctx.runtime_platforms:
        if ctx.enable_themida and not ctx.pyarmor_platform.startswith('win'):
            raise CliError('--enable_themida only works for Windows')

    if ctx.cmd_options['no_runtime'] and not ctx.runtime_outer:
        raise CliError('--no_runtime need pass outer key by --outer')

    if ctx.runtime_outer:
        if os.path.exists(ctx.runtime_outer):
            keyname = os.path.join(ctx.runtime_outer, ctx.runtime_keyfile)
            if not os.path.exists(keyname):
                raise CliError('no runtime key in "%s"', ctx.runtime_outer)
        else:
            try:
                ctx.read_outer_info(ctx.runtime_outer)
            except FileNotFoundError:
                raise CliError('no outer key "%s" found, please generated it '
                               'by "pyarmor gen key"', ctx.runtime_outer)


def cmd_gen(ctx, args):
    from .generate import Builder

    options = format_gen_args(ctx, args)
    logger.debug('command options: %s', options)
    ctx.push(options)
    check_gen_context(ctx)

    builder = Builder(ctx)

    if args.inputs[0].lower() in ('key', 'k'):
        _cmd_gen_key(builder, options)
    elif args.inputs[0].lower() in ('runtime', 'run', 'r'):
        _cmd_gen_runtime(builder, options)
    else:
        builder.process(options, pack=args.pack)


def cmd_cfg(ctx, args):
    scope = 'global' if args.scope else 'local'
    cfg = Configer(ctx, encoding=args.encoding)
    name = 'clear' if args.clear else 'remove' if args.remove else 'run'
    getattr(cfg, name)(args.section, args.options, scope == 'local', args.name)


def cmd_reg(ctx, args):
    regfile = args.regfile
    regname = args.regname if args.regname else ''
    product = args.product if args.product else 'non-profits'

    reg = LocalRegister(ctx) if args.dry else RealRegister(ctx)
    reg.check_args(args)

    meth = 'upgrade' if args.upgrade else 'register'
    getattr(reg, meth)(regfile, regname, product)

    logger.info('\n%s', reg)


def main_parser():
    parser = argparse.ArgumentParser(
        prog='pyarmor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '-v', '--version', action='store_true',
        help='show version information and exit'
    )
    parser.add_argument(
        '-q', '--silent', action='store_true',
        help='suppress all normal output'
    )
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='print debug informations in the console'
    )
    parser.add_argument(
        '-i', dest='interactive', action='store_true',
        help='interactive mode'
    )
    parser.add_argument('--home', help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(
        title='The most commonly used pyarmor commands are',
        metavar=''
    )

    gen_parser(subparsers)
    reg_parser(subparsers)
    cfg_parser(subparsers)

    return parser


def gen_parser(subparsers):
    '''generate obfuscated scripts and all required runtime files
    pyarmor gen <options> <scripts>

generate runtime key only
    pyarmor gen key <options> [NAME]

generate runtime package only
    pyarmor gen runtime <options>'''
    cparser = subparsers.add_parser(
        'gen',
        aliases=['generate', 'g'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=gen_parser.__doc__,
        help='generate obfuscated scripts and required runtime files'
    )

    cparser.add_argument('-O', '--output', metavar='PATH', help='output path')

    group = cparser.add_argument_group(
        'action arguments'
    ).add_mutually_exclusive_group()
    group.add_argument(
        '--pack', metavar='BUNDLE',
        help='pack obfuscated script'
    )
    group.add_argument(
        '--no-runtime', action='store_true',
        help='do not generate runtime package'
    )

    group = cparser.add_argument_group('obfuscation arguments')
    group.add_argument(
        '-r', '--recursive', action='store_true', default=None,
        help='search scripts in recursive mode'
    )
    group.add_argument(
        '-a', '--all', dest='findall', action='store_true', default=None,
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--include', dest='includes', metavar='PATTERN', action='append',
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--exclude', dest='excludes', metavar='PATTERN', action='append',
        help=argparse.SUPPRESS
    )

    group.add_argument(
        '--obf-module', type=int, default=None, choices=(0, 1),
        help='obfuscate module level code'
    )
    group.add_argument(
        '--obf-code', type=int, default=None, choices=(0, 1),
        help='obfuscate each function'
    )
    group.add_argument(
        '--no-wrap', action='store_true', default=None,
        help='do not wrap function',
    )

    group.add_argument(
        '--mix-str', action='store_true', default=None,
        help='protect string constant',
    )
    group.add_argument(
        '--mix-name', action='store_true', default=None,
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--enable-bcc', action='store_true', default=None,
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--enable-rft', action='store_true', default=None,
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--enable-jit', action='store_true', default=None,
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--enable-themida', action='store_true', default=None,
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--assert-call', action='store_true', default=None,
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--assert-import', action='store_true', default=None,
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--enable', action='append', dest='enables',
        choices=('jit', 'bcc', 'rft', 'themida'),
        help='enable different obfuscation features',
    )

    group.add_argument(
        '--restrict', type=int, default=None, choices=(0, 1, 2),
        dest='restrict_module', help='restrict obfuscated scripts'
    )

    group = cparser.add_argument_group('runtime package arguments')
    group.add_argument(
        '-i', dest='relative_import', action='store_const',
        default=None, const=1,
        help='import runtime package by relative way'
    )
    group.add_argument(
        '--relative', metavar='PREFIX',
        help='import runtime package with PREFIX'
    )
    group.add_argument(
        '--platform', dest='platforms', metavar='NAME', action='append',
        help='target platform to run obfuscated scripts, '
        'use this option multiple times for more platforms'
    )

    group = cparser.add_argument_group('runtime key arguments')
    group.add_argument(
        '--outer', metavar='NAME', dest='outer',
        help='use outer key for obfuscated scripts'
    )
    group.add_argument(
        '-e', '--expired', metavar='DATE',
        help='expired date of obfuscated scripts'
    )
    group.add_argument(
        '--period', type=int, metavar='N', dest='period',
        help='check runtime key in hours periodically'
    )
    group.add_argument(
        '-b', '--bind-device', dest='devices', metavar='DEV', action='append',
        help='bind obfuscated scripts to device'
    )
    group.add_argument(
        '--bind-interp', metavar='INTERP',
        help=argparse.SUPPRESS
    )
    group.add_argument(
        '--hook', metavar='HOOK',
        help=argparse.SUPPRESS
    )

    cparser.add_argument(
        'inputs', metavar='ARG', nargs='+',
        help='script, package or keyword "key", "runtime"'
    )

    cparser.set_defaults(func=cmd_gen)


def cfg_parser(subparsers):
    '''show all sections:
    pyarmor cfg

show all options in section `SECT`:
    pyarmor cfg SECT

show option `OPT` value:
    pyarmor cfg SECT OPT

change option value:
    pyarmor cfg SECT OPT=VALUE
    '''

    cparser = subparsers.add_parser(
        'cfg',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=cfg_parser.__doc__,
        help='show and config Pyarmor environments',
    )

    cparser.add_argument(
        '-p', dest='name',
        help='do everyting for special module or package'
    )
    cparser.add_argument(
        '-g', '--global', dest='scope', action='store_true',
        help='do everything in global settings, otherwise local settings'
    )
    group = cparser.add_mutually_exclusive_group()
    group.add_argument(
        '-r', '--remove', action='store_true',
        help='remove section or options'
    )
    group.add_argument(
        '--clear', action='store_true',
        help='clear configuration file'
    )
    cparser.add_argument(
        '--encoding',
        help='specify encoding to read configuration file'
    )

    cparser.add_argument('section', nargs='?', help='section name')
    cparser.add_argument(
        'options', nargs='*', metavar='option',
        help='option name or "name=value"'
    )

    cparser.set_defaults(func=cmd_cfg)


def reg_parser(subparsers):
    '''register or upgrade Pyarmor license

In the first time to register Pyarmor license, `-p` (product name) can
be set.

Once register successfully, product name can't be changed

Exception:

If product name is set to "TBD" at the first time, it can be changed
once later.

Suggestion:

Use option `-t` to check registration information first, make sure
everything is fine, then remove `-t` to register really

    '''
    cparser = subparsers.add_parser(
        'reg',
        aliases=['register', 'r'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=reg_parser.__doc__,
        help='register or upgrade Pyarmor license'
    )

    cparser.add_argument(
        '-r', '--regname', metavar='NAME',
        help=argparse.SUPPRESS
    )
    cparser.add_argument(
        '-p', '--product', metavar='NAME',
        help='license to this product'
    )
    cparser.add_argument(
        '-u', '--upgrade', action='store_true',
        help='upgrade license to pyarmor-pro'
    )
    cparser.add_argument(
        '-t', '--dry', action='store_true',
        help='dry run, not really register'
    )

    cparser.add_argument(
        'regfile', nargs=1, metavar='FILE',
        help='pyarmor-regcode-xxx.txt or pyarmor-regfile-xxxx.zip'
    )
    cparser.set_defaults(func=cmd_reg)


def log_settings(ctx, args):
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        handler = logging.FileHandler(ctx.debug_logfile, mode='w')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(handler)

    if args.silent:
        logging.getLogger().setLevel(100)


def log_exception(e):
    logger.critical('unknown error, please check pyarmor.error.log')
    handler = logging.FileHandler('pyarmor.error.log', mode='w')
    fmt = '%(process)d %(processName)s %(asctime)s'
    handler.setFormatter(logging.Formatter(fmt))
    log = logging.getLogger('Pyarmor.Error')
    log.propagate = False
    log.addHandler(logging.NullHandler())
    log.addHandler(handler)
    log.exception(e)


def print_version(ctx):
    info = 'Pyarmor %s' % ctx.version_info(), '', str(LocalRegister(ctx))
    print('\n'.join(info))


def get_home(args):
    home = args.home if args.home else os.getenv('PYARMOR_HOME')
    if not home:
        home = os.path.join('~', '.pyarmor')
    return os.path.abspath(os.path.expandvars(os.path.expanduser(home)))


def main_entry(argv):
    parser = main_parser()
    args = parser.parse_args(argv)

    if sys.version_info[0] == 2 or sys.version_info[1] < 7:
        raise CliError('only Python 3.7+ is supported now')

    home = get_home(args)
    ctx = Context(home)

    log_settings(ctx, args)

    if args.version:
        print_version(ctx)
        parser.exit()

    if args.interactive:
        return PyarmorShell(ctx).cmdloop()

    logger.info('Python %d.%d.%d', *sys.version_info[:3])
    logger.info('Pyarmor %s', ctx.version_info())

    logger.debug('native platform %s', ctx.native_platform)
    logger.debug('home path: %s', home)

    if hasattr(args, 'func'):
        args.func(ctx, args)
    else:
        parser.print_help()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)-8s %(message)s',
    )

    try:
        main_entry(sys.argv[1:])
    # TBD: comment for debug
    # except (CliError, RuntimeError) as e:
    #     logger.error(e)
    #     sys.exit(1)
    except Exception as e:
        log_exception(e)
        logger.error(e)
        sys.exit(2)


if __name__ == '__main__':
    main()