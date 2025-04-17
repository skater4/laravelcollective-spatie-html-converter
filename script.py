#!/usr/bin/env python3
import os
import re
import sys
from typing import List, Tuple, Optional


def split_args(s: str) -> List[str]:
    """
    Split a function-call argument string on top-level commas only
    (ignores commas inside (), [] or string literals).
    """
    parts: List[str] = []
    cur = ''
    paren = 0
    bracket = 0
    in_str: Optional[str] = None
    escape = False

    for c in s:
        if escape:
            cur += c
            escape = False
            continue
        if c == '\\':
            cur += c
            escape = True
            continue

        if in_str:
            cur += c
            if c == in_str:
                in_str = None
            continue

        if c in ('"', "'"):
            in_str = c
            cur += c
            continue

        if c == '(': paren += 1
        elif c == ')': paren -= 1
        elif c == '[': bracket += 1
        elif c == ']': bracket -= 1

        # top-level comma splits arguments
        if c == ',' and paren == 0 and bracket == 0:
            parts.append(cur.strip())
            cur = ''
        else:
            cur += c

    if cur.strip():
        parts.append(cur.strip())
    return parts


def extract_call_args(content: str, start: int) -> Tuple[str, int]:
    """
    From content[start:], find substring up to matching ')' at depth 0.
    Returns (args_str, index_of_closing_paren).
    """
    depth = 1
    in_str: Optional[str] = None
    escape = False
    i = start
    while i < len(content) and depth > 0:
        c = content[i]
        if escape:
            escape = False
        elif c == '\\':
            escape = True
        elif in_str:
            if c == in_str:
                in_str = None
        elif c in ('"', "'"):
            in_str = c
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        i += 1
    return content[start:i-1], i-1


def find_html_aliases(content: str) -> List[str]:
    pattern = re.compile(r"use\s+Collective\\Html\\HtmlFacade(?:\s+as\s+(\w+))?;", flags=re.IGNORECASE)
    aliases: List[str] = []
    for m in pattern.finditer(content):
        alias = m.group(1) if m.group(1) else "HtmlFacade"
        aliases.append(alias)
    return aliases


def convert_attributes(array_str: str) -> str:
    s = array_str.strip()
    if s.startswith('[') and s.endswith(']'):
        s = s[1:-1]
    parts = re.findall(r"(['\"])(\w+)\1\s*=>\s*(['\"])(.*?)\3", s)
    chain = ''
    for _, key, _, val in parts:
        chain += f"->{key}('{val}')"
    return chain


def replace_form_open(m: re.Match) -> str:
    args = m.group(1).strip()
    if args.startswith('[') and args.endswith(']'):
        return f"html()->form(){convert_attributes(args)}->open()"
    if args:
        return f"html()->form()->open({args})"
    return "html()->form()->open()"


def replace_form_close(_: re.Match) -> str:
    return "html()->form()->close()"


def replace_simple_field(method: str, rep: str, content: str) -> str:
    pat = rf"Form::{method}\(\s*([^,]+)\s*,\s*([^,\)]+)(?:\s*,\s*(\[[^\]]+\]))?\s*\)"
    def r(m: re.Match) -> str:
        a1, a2, at = m.group(1), m.group(2), m.group(3)
        res = f"html()->{rep}({a1}, {a2})"
        if at:
            res += convert_attributes(at)
        return res
    return re.sub(pat, r, content, flags=re.DOTALL)


def replace_single_arg_field(method: str, rep: str, content: str) -> str:
    pat = rf"Form::{method}\(\s*([^,\)]+)(?:\s*,\s*(\[[^\]]+\]))?\s*\)"
    def r(m: re.Match) -> str:
        n, at = m.group(1), m.group(2)
        res = f"html()->{rep}({n})"
        if at:
            res += convert_attributes(at)
        return res
    return re.sub(pat, r, content, flags=re.DOTALL)


def replace_form_select(content: str) -> str:
    pat = r"Form::select\(\s*([^,]+)\s*,\s*([^,]+)(?:\s*,\s*([^,\)]+))?(?:\s*,\s*(\[[^\]]+\]))?\s*\)"
    def r(m: re.Match) -> str:
        n, o, s, at = m.group(1), m.group(2), m.group(3), m.group(4)
        res = f"html()->select({n}, {o})"
        if s: res += f"->selected({s})"
        if at: res += convert_attributes(at)
        return res
    return re.sub(pat, r, content, flags=re.DOTALL)


def replace_form_radio(content: str) -> str:
    pat = r"Form::radio\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,\)]+)(?:\s*,\s*(\[[^\]]+\]))?\s*\)"
    def r(m: re.Match) -> str:
        n, v, ck, at = m.group(1), m.group(2), m.group(3), m.group(4)
        res = f"html()->radio({n}, {v}, {ck})"
        if at: res += convert_attributes(at)
        return res
    return re.sub(pat, r, content, flags=re.DOTALL)


def replace_form_checkbox(content: str) -> str:
    pat = r"Form::checkbox\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,\)]+)(?:\s*,\s*(\[[^\]]+\]))?\s*\)"
    def r(m: re.Match) -> str:
        n, v, ck, at = m.group(1), m.group(2), m.group(3), m.group(4)
        res = f"html()->checkbox({n}, {v}, {ck})"
        if at: res += convert_attributes(at)
        return res
    return re.sub(pat, r, content, flags=re.DOTALL)


def replace_form_textarea(content: str) -> str:
    pat = r"Form::textarea\(\s*([^,]+)\s*,\s*([^,]+)(?:\s*,\s*(\[[^\]]+\]))?\s*\)"
    def r(m: re.Match) -> str:
        n, v, at = m.group(1), m.group(2), m.group(3)
        res = f"html()->textarea({n}, {v})"
        if at: res += convert_attributes(at)
        return res
    return re.sub(pat, r, content, flags=re.DOTALL)


def replace_form_number(content: str) -> str:
    pat = r"Form::number\(\s*([^,]+)\s*,\s*([^,]+)(?:\s*,\s*(\[[^\]]+\]))?\s*\)"
    def r(m: re.Match) -> str:
        n, v, at = m.group(1), m.group(2), m.group(3)
        res = f"html()->number({n}, {v})"
        if at: res += convert_attributes(at)
        return res
    return re.sub(pat, r, content, flags=re.DOTALL)


def extract_and_replace_calls(content: str, alias: str, method: str) -> str:
    call = f"{alias}::{method}"
    out = ''
    idx = 0
    while True:
        pos = content.find(call + '(', idx)
        if pos == -1:
            out += content[idx:]
            break
        out += content[idx:pos]
        args_start = pos + len(call) + 1
        args_str, args_end = extract_call_args(content, args_start)
        parts = split_args(args_str)
        if method == 'linkRoute':
            route_name = parts[0] if len(parts) > 0 else "''"
            params     = parts[1] if len(parts) > 1 else "[]"
            attrs      = parts[2] if len(parts) > 2 else "[]"
            title      = parts[3] if len(parts) > 3 else "''"
            code = f"html()->a()->route({route_name}, {params})"
            code += convert_attributes(attrs) if attrs.startswith('[') else f"->attributes({attrs})"
            code += f"->html({title})"
        else:
            href  = parts[0] if len(parts) > 0 else "''"
            title = parts[1] if len(parts) > 1 else "''"
            attrs = parts[2] if len(parts) > 2 else ''
            code = f"html()->a({href}, {title})"
            if attrs.startswith('['):
                code += convert_attributes(attrs)
            elif attrs:
                code += f"->attributes({attrs})"
        out += code
        idx = args_end + 1
    return out


def replace_alias_generic(content: str, alias: str) -> str:
    pattern = rf"{alias}::(\w+)\((.*?)\)"
    def repl(m: re.Match) -> str:
        method, args = m.group(1), m.group(2)
        if method in ('link', 'linkRoute'):
            return m.group(0)
        return f"html()->{method}({args})"
    return re.sub(pattern, repl, content, flags=re.DOTALL)


def convert_code(content: str) -> str:
    for alias in find_html_aliases(content):
        content = extract_and_replace_calls(content, alias, 'linkRoute')
        content = extract_and_replace_calls(content, alias, 'link')
        content = replace_alias_generic(content, alias)

    content = re.sub(r"use\s+Collective\\Html\\HtmlFacade(?:\s+as\s+\w+)?;\s*\n", "", content, flags=re.IGNORECASE)
    content = re.sub(r"Form::open\((.*?)\)", replace_form_open, content, flags=re.DOTALL)
    content = re.sub(r"Form::close\(\)", replace_form_close, content)
    content = replace_simple_field('hidden', 'hidden', content)
    content = replace_simple_field('email', 'email', content)
    content = replace_single_arg_field('password', 'password', content)
    content = replace_single_arg_field('submit', 'submit', content)
    content = replace_form_select(content)
    content = replace_form_radio(content)
    content = replace_form_checkbox(content)
    content = replace_single_arg_field('button', 'button', content)
    content = replace_form_textarea(content)
    content = replace_form_number(content)
    for f in ('file', 'date', 'time', 'url', 'search'):
        content = replace_single_arg_field(f, f, content)

    return content


def process_directory(root_dir: str) -> None:
    php_files = [os.path.join(d, f)
                 for d, _, fs in os.walk(root_dir)
                 for f in fs if f.endswith(('.php', '.blade.php'))]
    total = len(php_files)
    processed = 0
    for path in php_files:
        try:
            src = open(path, encoding='utf-8').read()
        except Exception as e:
            print(f"Не удалось прочитать {path}: {e}")
            processed += 1
            print(f"Обработано: {processed}/{total}\r", end='')
            continue

        dst = convert_code(src)
        if dst != src:
            try:
                open(path, 'w', encoding='utf-8').write(dst)
            except Exception as e:
                print(f"Не удалось записать {path}: {e}")

        processed += 1
        print(f"Обработано: {processed}/{total}\r", end='')
    print("\nГотово.")

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    process_directory(target)
