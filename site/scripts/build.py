"""Build and validate the current-toolchain website into ignored site/dist."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from check_dewy_examples import check_all, compiler_path
from check_links import LinkParser
from highlight_dewy import highlight_tree
import site_coverage

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT/'site'
DIST = SITE_ROOT/'dist'
STATIC = SITE_ROOT/'static'
LEARN = SITE_ROOT/'learn'
REFERENCE = SITE_ROOT/'reference'


def run(command, **kwargs):
    print('+ '+' '.join(map(str,command)), flush=True)
    return subprocess.run(command, cwd=REPO_ROOT, check=True, **kwargs)


def require_tool(name):
    value = shutil.which(name)
    if not value: raise SystemExit(f'Required tool {name!r} is missing; see site/README.md')
    return value


def copy_install_scripts():
    for name in ('install.sh','install.ps1'):
        source = REPO_ROOT/name
        if source.exists(): shutil.copy2(source,DIST/name)
        else: print(f'warning: {name} is absent; installer agent must supply it',file=sys.stderr)
    channel = REPO_ROOT/'tools/compiler/channel.py'
    tag = os.environ.get('DEWY_CHANNEL_TAG')
    if channel.is_file() and (tag or os.environ.get('CI')):
        # A deploy names its release; other CI builds point at the newest published toolchain.
        which=['--tag',tag] if tag else ['--latest']
        if subprocess.call([sys.executable,'-m','tools.compiler.channel',*which,'--output',str(DIST/'toolchain-channel.txt')],cwd=REPO_ROOT):
            if tag: sys.exit(f'error: cannot write the channel for {tag}')
            print('warning: no toolchain-channel.txt: no published toolchain release yet',file=sys.stderr)
    else:
        print('warning: no toolchain-channel.txt: supply channel.py and DEWY_CHANNEL_TAG after publishing a complete release',file=sys.stderr)


def channel_release(identity):
    sys.path.insert(0,str(REPO_ROOT))
    from tools.compiler.channel import parse
    return parse(identity)[0]


def channel_html(identity):
    """Install-page availability text: the channel's release, or the checkout fallback."""
    if identity is None:
        return '<p class="notice">No toolchain release is attached to this website build. Use the <a href="#checkout">checkout instructions</a> below.</p>'
    tag=channel_release(identity)
    return (f'<p>Current release: <code>{html.escape(tag)}</code>. The installers below download it and verify every archive against the '
            '<a href="/toolchain-channel.txt">published toolchain channel</a>.</p><details><summary>Release identity and digests</summary><pre>'
            +html.escape(identity)+'</pre></details>')


def build_book(source, destination, mdbook, scratch):
    # Expand generated prose in a disposable source copy; never edit tracked source.
    book = scratch/source.name
    shutil.copytree(source,book,ignore=shutil.ignore_patterns('book','__pycache__'))
    # mdBook resolves theme paths relative to the copied book.
    for p in (book/'src').rglob('*.md'):
        value = p.read_text()
        for key,text in REPLACEMENTS.items():value=value.replace(f'<!-- generated: {key} -->',text)
        p.write_text(value)
    run([mdbook,'build',str(book),'--dest-dir',str(destination)])
    # mdBook 0.4 prefixes root-relative Markdown URLs in nested print chapters.
    # Keep the printable route, repairing only the spurious directory + slash.
    printable = destination/'print.html'
    printable.write_text(re.sub(r'(href=["\'])(?:[^/:"\']+/)+/([^"\']*)',
                                r'\1/\2', printable.read_text()))


def redirect(target, aliases):
    safe = html.escape(target,quote=True)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Archived page — Dewy</title><link rel="canonical" href="{safe}"><meta http-equiv="refresh" content="0; url={safe}"></head><body><main><h1>This page has moved</h1><p><a data-redirect="{safe}" href="{safe}">Continue to the archived page</a>.</p>{''.join(f'<span id="{html.escape(a,quote=True)}"></span>' for a in aliases)}</main><script>const target=new URL({json.dumps(target)},location.href);if(location.hash)target.hash=location.hash;location.replace(target.href);</script></body></html>'''


def preserve_routes():
    doc=json.loads((SITE_ROOT/'routes.json').read_text())
    for route,target in doc['redirects'].items():
        dest=DIST/route;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(redirect(target,doc['aliases'].get(route,[])))
    # Retired local destinations retain incoming fragment names too.
    archive_aliases=set()
    for route,target in doc['redirects'].items():
        if target=='/archive/':archive_aliases.update(doc['aliases'].get(route,[]))
    doc['aliases'].setdefault('archive/index.html',[]).extend(archive_aliases)
    for route,aliases in doc['aliases'].items():
        dest=DIST/route
        if not dest.is_file():raise ValueError(f'preserved route missing: {route}')
        source=dest.read_text();parser=LinkParser();parser.feed(source)
        missing=set(aliases)-parser.ids
        spans=''.join(f'<span class="anchor-alias" id="{html.escape(a,quote=True)}"></span>' for a in sorted(missing))
        source=re.sub(r'(<main\b[^>]*>)', lambda match: match[0]+spans, source, count=1) if '<main' in source else source.replace('</body>',spans+'</body>',1)
        dest.write_text(source)


def build_playground(compiler, scratch, node):
    from tools.cases import Scripts
    examples=json.loads((SITE_ROOT/'playground/examples.json').read_text())
    cards=[];results=[]
    for e in examples:
        if e['mode'] not in ('run','check') or e['target'] != 'wasm-release':
            raise ValueError('playground entries must declare check or run, and wasm-release')
        if 'source_path' in e:
            source=REPO_ROOT/e['source_path']
        else:
            source=scratch/(e['id']+'.dewy');source.write_text(e['source'])
        run([str(compiler),'check',str(source)])
        output=DIST/'playground/programs'/e['id']
        output.parent.mkdir(parents=True,exist_ok=True)
        run([str(compiler),'build',str(source),'--target','wasm','--release','-o',str(output)])
        page=output.with_suffix('.html')
        if e['mode']=='run':
            scripts=Scripts();scripts.feed(page.read_text());runner=scratch/(e['id']+'.cjs')
            runner.write_text('\n'.join(scripts.parts))
            ran=run([node,str(runner)],capture_output=True,timeout=15)
            if ran.stdout.decode()!=e['stdout']:raise ValueError(f'wasm {e["id"]}: stdout mismatch: {ran.stdout!r}')
        # Browser examples get an opaque origin, no network, and bounded visible output.
        bounded='''<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'unsafe-inline'; img-src data:"><script>addEventListener('DOMContentLoaded',()=>{const log=document.getElementById('log');if(!log)return;new MutationObserver(()=>{while(log.childNodes.length>200)log.firstChild.remove();for(const n of log.childNodes)if(n.textContent.length>8192)n.textContent=n.textContent.slice(0,8192)}).observe(log,{childList:true});});</script>'''
        page.write_text(page.read_text().replace('<head>','<head>'+bounded,1))
        result={'id':e['id'],'status':'tested example','mode':e['mode'],'target':'wasm-release',
                'runner':'Node' if e['mode']=='run' else 'compiler (check and wasm build only)'}
        if e['mode']=='run':result['stdout']=e['stdout']
        results.append(result)
        note=('Expected stdout: <code>'+html.escape(e['stdout'].strip())+'</code>') if e['mode']=='run' else html.escape(e['instructions'])
        displayed = '<pre><code class="language-dewy">'+html.escape(source.read_text())+'</code></pre>'
        if 'source_path' in e:
            displayed = '<details><summary>Source</summary>'+displayed+'<p><a href="https://github.com/david-andrew/dewy-lang/tree/master/examples/">Source and companion modules</a></p></details>'
        cards.append(f'''<article class="example-card"><h3>{html.escape(e['title'])}</h3>{displayed}<p>{note}</p><div class="button-row"><button class="button primary" data-program="/playground/programs/{e['id']}.html">Run example</button><button class="button" data-stop>Stop</button></div><p role="status" data-run-status>Ready</p><div data-run-host></div></article>''')
    return '<div class="example-grid">'+''.join(cards)+'</div><script src="/assets/js/playground.js" defer></script>',results


def write_sitemap():
    urls=[]
    for path in sorted(DIST.rglob('*.html')):
        route=path.relative_to(DIST).as_posix();parser=LinkParser();parser.feed(path.read_text())
        if parser.redirect or path.name in ('404.html','print.html','toc.html') or '/programs/' in '/'+route:continue
        route=route.removesuffix('index.html')
        urls.append(f'<url><loc>https://dewy-lang.org/{escape(route)}</loc></url>')
    (DIST/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(urls)+'</urlset>\n')

REPLACEMENTS={}

def main(argv=None):
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--compiler',help='pinned standalone bin/dewy-core')
    options=cli.parse_args(argv)
    mdbook=require_tool('mdbook');node=require_tool('node')
    compiler=compiler_path(options.compiler or os.environ.get('DEWY_SITE_COMPILER'))
    if DIST.exists():shutil.rmtree(DIST)
    shutil.copytree(STATIC,DIST,ignore=shutil.ignore_patterns('designs'))
    scratch=DIST/'.work';scratch.mkdir();os.environ['TMPDIR']=str(scratch)
    # Reset tempfile's cached default for repeated watch builds.
    import tempfile
    tempfile.tempdir=str(scratch)
    (DIST/'.nojekyll').write_text('')
    copy_install_scripts()
    examples=check_all(compiler,scratch)
    coverage=site_coverage.collect(compiler,DIST,scratch)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO_ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=REPO_ROOT,text=True))
    run_url=(f'{os.environ.get("GITHUB_SERVER_URL","https://github.com")}/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}' if os.environ.get('GITHUB_RUN_ID') else None)
    coverage.update({'schema':1,'revision':revision,'source_dirty':dirty,'generated_at':datetime.now(timezone.utc).isoformat(),
                     'release_tag':os.environ.get('DEWY_CHANNEL_TAG'),'run_url':run_url,'examples':examples})
    playground,web=build_playground(compiler,scratch,node);coverage['web']=web
    ladder=coverage['ladder'];rows=ladder['results']
    def esc(s):return html.escape(str(s))
    ladder_html='<p>Native release on '+esc(ladder['host'])+'. Design '+str(sum(r['ok'] for r in rows if r['version']=='design'))+'/'+str(len(rows)//2)+'; core '+str(sum(r['ok'] for r in rows if r['version']=='core'))+'/'+str(len(rows)//2)+'.</p><details><summary>Individual programs and failures</summary><ul>'+''.join(f'<li>{esc(r["program"])} / {r["version"]}: {"pass" if r["ok"] else "FAIL — "+esc(r["error"])}</li>' for r in rows)+'</ul></details>'
    failures=[r for r in rows if r['version']=='design' and not r['ok']]
    if failures:
        ladder_html += '<h3>Known design failures</h3><ul>'+''.join(
            f'<li><code>{esc(r["program"])}</code>: {esc(r["error"])}</li>' for r in failures)+'</ul>'
    counts={m:sum(e['mode']==m for e in examples) for m in ('run','check','reject','design-only')}
    example_html='<p>'+', '.join(f'{v} {k}' for k,v in counts.items())+'. Check/reject rows measure diagnostics and checking; only run rows compare stdout.</p><details><summary>Exact snippet IDs</summary><ul>'+''.join(f'<li>{esc(e["id"])}: {e["mode"]} — {e["status"]}</li>' for e in examples)+'</ul></details>'
    channel_exists=(DIST/'toolchain-channel.txt').is_file()
    channel_identity = (DIST/'toolchain-channel.txt').read_text() if channel_exists else None
    coverage['channel_identity'] = channel_identity
    if channel_exists: coverage['release_tag'] = channel_release(channel_identity)
    (DIST/'coverage/index.json').write_text(json.dumps(coverage,indent=2)+'\n')
    REPLACEMENTS.update({
      'coverage':site_coverage.render(coverage,revision),
      'revisions':f'<p>Website source: <code>{revision}</code>{" (working tree modified)" if dirty else ""}. Generated {esc(coverage["generated_at"])}.</p><p>Compiler SHA-256: <code class="digest">{ladder["compiler_sha256"]}</code>. Target: native-release on {esc(ladder["host"])}.</p><p>Downloadable release: {esc(coverage["release_tag"]) if channel_exists else "no channel generated by this build"}.</p>'+ ('<details><summary>Downloadable release identity and digests</summary><pre>'+esc(channel_identity)+'</pre></details>' if channel_exists else '')+ (f'<p><a href="{esc(run_url)}">Build run</a></p>' if run_url else '<p>Local build; no CI run attached.</p>')+'<p><a href="/coverage/index.json">Machine-readable coverage</a> · <a href="/coverage/ladder.json">Fresh ladder results</a></p>',
      'channel':channel_html(channel_identity),
      'examples':example_html,'ladder':ladder_html,'playground':playground,
      'web':'<ul>'+''.join(f'<li>{esc(r["id"])}: tested example · wasm-release · {esc(r["runner"])}</li>' for r in web)+'</ul>'})
    for p in DIST.rglob('*.html'):
        text=p.read_text()
        for key,value in REPLACEMENTS.items():text=text.replace(f'<!-- generated: {key} -->',value)
        p.write_text(text)
    build_book(LEARN,DIST/'learn',mdbook,scratch)
    build_book(REFERENCE,DIST/'reference',mdbook,scratch)
    preserve_routes()
    highlight_tree(DIST,node=node)
    shutil.rmtree(scratch)
    write_sitemap()
    run([sys.executable,'site/scripts/check_links.py',str(DIST)])
    print(f'Built site: {DIST}; {len(list(DIST.rglob("*.html")))} HTML routes',flush=True)

if __name__=='__main__':main()
