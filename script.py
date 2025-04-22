#!/usr/bin/env python3
import os
import re
import sys
from typing import List, Tuple, Optional


def split_args(s: str) -> List[str]:
    """
    Split on top‐level commas only (ignores commas inside (), [] or string literals).
    """
    parts: List[str] = []
    cur = ''
    paren = bracket = 0
    in_str: Optional[str] = None
    escape = False

    for c in s:
        if escape:
            cur += c; escape = False; continue
        if c == '\\':
            cur += c; escape = True; continue
        if in_str:
            cur += c
            if c == in_str: in_str = None
            continue
        if c in ('"', "'"):
            in_str = c; cur += c; continue

        if c == '(':
            paren += 1
        elif c == ')':
            paren -= 1
        elif c == '[':
            bracket += 1
        elif c == ']':
            bracket -= 1

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
    From content[start:], read until the matching ')' at depth 0.
    Returns (args_str_without_parens, index_of_closing_paren).
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


def convert_attributes(array_str: str) -> str:
    """
    "[ 'class'=>'btn', 'id'=>'x' ]"    → "->class('btn')->id('x')"
    "array('readonly'=>'readonly')"    → "->attribute('readonly','readonly')"
    """
    s = array_str.strip()
    if s.startswith('array(') and s.endswith(')'):
        s = s[len('array('):-1]
    elif s.startswith('[') and s.endswith(']'):
        s = s[1:-1]
    else:
        return ''

    parts = re.findall(r"(['\"])(.+?)\1\s*=>\s*(['\"])(.*?)\3", s)
    chain = ''
    for _, key, _, val in parts:
        if key in ('class', 'id', 'name', 'type', 'value', 'placeholder'):
            chain += f"->{key}('{val}')"
        else:
            chain += f"->attribute('{key}', '{val}')"
    return chain


def map_form_method_to_html(method: str, parts: List[str]) -> str:
    """
    Convert Form::<method>(...) → html()-><method>(...)->...attributes
    """
    if method == 'select':
        name = parts[0] if len(parts) > 0 else "''"
        opts = parts[1] if len(parts) > 1 else "[]"
        sel  = parts[2] if len(parts) > 2 else None
        at   = parts[3] if len(parts) > 3 else None
        code = f"html()->select({name}, {opts}"
        if sel:
            code += f", {sel}"
        code += ")"
        if at:
            code += convert_attributes(at)
        return code

    if method in ('radio', 'checkbox'):
        name = parts[0] if len(parts)>0 else "''"
        val  = parts[1] if len(parts)>1 else "''"
        ck   = parts[2] if len(parts)>2 else 'false'
        at   = parts[3] if len(parts)>3 else None
        code = f"html()->{method}({name}, {val}, {ck})"
        if at:
            code += convert_attributes(at)
        return code

    if method in ('textarea','number','email','hidden','search','file','date','time','url'):
        name = parts[0] if len(parts)>0 else "''"
        val  = parts[1] if len(parts)>1 else None
        at   = parts[2] if len(parts)>2 else None
        code = f"html()->{method}({name}"
        if val is not None:
            code += f", {val}"
        code += ")"
        if at:
            code += convert_attributes(at)
        return code

    if method in ('text','password'):
        name = parts[0] if len(parts)>0 else "''"
        val = at = None
        if len(parts) > 1:
            if re.match(r"^\s*(?:array\(|\[)", parts[1]):
                at = parts[1]
            else:
                val = parts[1]
        if len(parts) > 2:
            at = parts[2]
        code = f"html()->{method}({name}"
        if val is not None:
            code += f", {val}"
        code += ")"
        if at:
            code += convert_attributes(at)
        return code

    if method in ('submit','button'):
        val = parts[0] if len(parts)>0 else "''"
        at  = parts[1] if len(parts)>1 else None
        code = f"html()->{method}({val})"
        if at:
            code += convert_attributes(at)
        return code

    if method == 'open':
        arg = parts[0] if len(parts)>0 else ''
        if re.match(r"^\s*(?:array\(|\[)", arg):
            return f"html()->form(){convert_attributes(arg)}->open()"
        return f"html()->form()->open({arg})"

    if method == 'close':
        return "html()->form()->close()"

    # fallback
    args = ", ".join(parts)
    return f"html()->{method}({args})"


def replace_all_form_calls(content: str) -> str:
    out = ''
    idx = 0
    while True:
        pos = content.find('Form::', idx)
        if pos == -1:
            out += content[idx:]
            break
        out += content[idx:pos]
        m = re.match(r'Form::(\w+)', content[pos:])
        if not m:
            idx = pos + len('Form::')
            continue
        method = m.group(1)
        start = pos + m.end()
        while start < len(content) and content[start].isspace():
            start += 1
        if start >= len(content) or content[start] != '(':
            idx = pos + m.end()
            continue
        args_str, end = extract_call_args(content, start+1)
        parts = split_args(args_str)
        out += map_form_method_to_html(method, parts)
        idx = end + 1
    return out


def map_html_method_to_html(method: str, parts: List[str]) -> str:
    """
    Convert Html::link(...) and Html::linkRoute(...) → html()->a()...
    """
    if method == 'linkRoute':
        name   = parts[0] if len(parts)>0 else "''"
        title  = parts[1] if len(parts)>1 else "''"
        params = parts[2] if len(parts)>2 else "[]"
        attrs  = parts[3] if len(parts)>3 else None
        escape = parts[5] if len(parts)>5 else 'true'
        code = f"html()->a()->route({name}, {params})"
        if escape.strip().lower() in ('false','0'):
            code += f"->html({title})"
        else:
            code += f"->text({title})"
        if attrs:
            code += convert_attributes(attrs)
        return code

    if method == 'link':
        href   = parts[0] if len(parts)>0 else "''"
        title  = parts[1] if len(parts)>1 else "''"
        attrs  = parts[2] if len(parts)>2 else None
        escape = parts[3] if len(parts)>3 else 'true'
        code = f"html()->a({href}, {title})"
        if escape.strip().lower() in ('false','0'):
            code = code.rsplit(',',1)[0] + ')'  # remove auto-escaped text
            code += f"->html({title})"
        if attrs:
            code += convert_attributes(attrs)
        return code

    # fallback
    args = ", ".join(parts)
    return f"Html::{method}({args})"


def replace_all_html_calls(content: str) -> str:
    out = ''
    idx = 0
    while True:
        pos = content.find('Html::', idx)
        if pos == -1:
            out += content[idx:]
            break
        out += content[idx:pos]
        m = re.match(r'Html::(\w+)', content[pos:])
        if not m:
            idx = pos + len('Html::')
            continue
        method = m.group(1)
        start = pos + m.end()
        while start < len(content) and content[start].isspace():
            start += 1
        if start >= len(content) or content[start] != '(':
            idx = pos + m.end()
            continue
        args_str, end = extract_call_args(content, start+1)
        parts = split_args(args_str)
        out += map_html_method_to_html(method, parts)
        idx = end + 1
    return out


def convert_code(content: str) -> str:
    # normalize "\Form::" → "Form::" and remove old import
    content = content.replace('\\Form::', 'Form::')
    content = re.sub(
        r"use\s+Collective\\Html\\HtmlFacade(?:\s+as\s+\w+)?;\s*\n",
        "",
        content,
        flags=re.IGNORECASE
    )
    # Form:: → html()
    content = replace_all_form_calls(content)
    # Html:: → html()->a() / route()
    content = replace_all_html_calls(content)
    return content


def process_directory(root_dir: str) -> None:
    php_files = [
        os.path.join(d, f)
        for d, _, fs in os.walk(root_dir)
        for f in fs if f.endswith(('.php', '.blade.php'))
    ]
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
