#!/usr/bin/env python3
"""Build/check all targets. Add --browser for Chromium integration checks.

The game has no Python or Playwright runtime dependency. This is development
verification only. Browser checks require `pip install playwright` followed by
`playwright install chromium`.
"""
from __future__ import annotations
import argparse
import asyncio
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path('udewy/tests/hollow_signal')
CACHE = ROOT / '__dewycache__' / SOURCE


def build(name: str, target: str) -> None:
    result = subprocess.run(
        [sys.executable, '-m', 'udewy', '-c', '--target', target,
         str(SOURCE / f'{name}.udewy')], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)


def native(name: str) -> str:
    return subprocess.check_output([str(CACHE / name)], cwd=ROOT, timeout=30).decode()


async def browser_checks(expected: dict[str, str]) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 810})
        errors: list[str] = []
        logs: list[str] = []
        page.on('console', lambda message: logs.append(message.text) if message.type == 'log' and not message.text.startswith('Exit code:') else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        for name, output in expected.items():
            logs.clear()
            await page.goto((CACHE / f'{name}.html').as_uri())
            await page.wait_for_function('wasmInstance !== null')
            actual = ''.join(logs)
            assert actual == output, (name, actual, output)
            print(f'PASS {name}: WebAssembly output matches native exactly')

        await page.goto((CACHE / 'hollow_signal.html').as_uri())
        await page.wait_for_function('frameCount > 3')
        # Observe state without editing it. The generated new_game function's
        # first global store is mode; the following scalar globals are contiguous.
        wat = (CACHE / 'hollow_signal.wat').read_text()
        reset = wat.split('  (func $new_game ', 1)[1].split('\n  (func ', 1)[0]
        base = int(re.search(r'local\.set \$swap0\s+i32\.const (\d+)\s+local\.get \$swap0\s+i64\.store', reset)[1])
        declarations = re.findall(r'^let (\w+):int =', (ROOT / SOURCE / 'core.udewy').read_text(), re.M)
        fields = declarations[declarations.index('mode'):]
        addresses = {name: base + i * 8 for i, name in enumerate(fields)}
        await page.evaluate('''a => { window.hsRead = n => Number(new DataView(memory.buffer).getBigInt64(a[n], true)); }''', addresses)
        read = lambda name: page.evaluate('n => hsRead(n)', name)
        assert await read('mode') == 0
        assert await read('hp') == 6
        await page.screenshot(path=str(CACHE / 'title.png'))
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(80)
        assert await read('mode') == 1
        x = await read('px')
        await page.keyboard.down('d')
        await page.keyboard.down('j')
        await page.wait_for_timeout(550)
        await page.keyboard.up('d')
        assert await read('px') > x + 20 * 256
        await page.keyboard.press('Space')
        await page.wait_for_timeout(60)
        assert await read('dash_serial') == 1
        await page.wait_for_function("hsRead('kills') > 0", timeout=7000)
        assert await read('kills') > 0
        assert await page.evaluate('audioQueueRing.some(x => x !== 0)')
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(80)
        assert await read('mode') == 3
        paused = await read('run_ticks')
        await page.wait_for_timeout(120)
        assert await read('run_ticks') == paused
        await page.screenshot(path=str(CACHE / 'pause.png'))
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(80)
        assert await read('mode') == 1
        await page.keyboard.press('m')
        await page.wait_for_timeout(80)
        assert await read('muted') == 1
        await page.keyboard.up('j')
        await page.screenshot(path=str(CACHE / 'play.png'))
        await page.set_viewport_size({'width': 900, 'height': 900})
        await page.wait_for_timeout(80)
        bounds = await page.locator('canvas').bounding_box()
        assert abs(bounds['width'] / bounds['height'] - 16 / 9) < 0.01, bounds
        assert not errors, errors
        print('PASS browser: movement, firing, dash, pause/resume, PCM audio, mute, aspect ratio; no runtime errors')
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--sdl', action='store_true', help='open a real SDL window for the integration smoke test')
    args = parser.parse_args()
    outputs: dict[str, str] = {}
    for name in ['test_core', 'test_frame']:
        for target in ['x86_64', 'c', 'wasm32']:
            build(name, target)
            if target != 'wasm32':
                output = native(name)
                assert 'FAIL' not in output
                if name in outputs:
                    assert outputs[name] == output, f'{name}: C/native mismatch'
                outputs[name] = output
        print(f'PASS {name}: x86_64 and C agree; WebAssembly compiled')
    build('test_render', 'x86_64')
    frames = subprocess.check_output([str(CACHE / 'test_render')], timeout=20)
    assert len(frames) == 480 * 270 * 4 * 6
    assert all(v == 255 for v in frames[3::4]), 'uninitialized/incorrect framebuffer alpha'
    (CACHE / 'scenes.rgba').write_bytes(frames)
    print('PASS renderer: six full scenes; framebuffer guards and RGBA alpha intact')
    for target in ['c', 'x86_64', 'wasm32']:
        build('hollow_signal', target)
        print(f'PASS game build: {target}')
    if args.sdl:
        build('test_sdl', 'x86_64')
        native('test_sdl')
        print('PASS SDL: window, rendering, resize/aspect ratio, audio calls, quit; no GL errors')
    if args.browser:
        asyncio.run(browser_checks(outputs))
    print(f'Artifacts: {CACHE}')


if __name__ == '__main__':
    main()
