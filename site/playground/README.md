# µDewy playground

The website playground is generated from
`udewy/tests/web/playground.udewy`. Keeping the executable source beside the
µDewy web fixtures lets compiler parity tests and the public site exercise the
same application.

`site/scripts/build.py` performs the complete build and copies the resulting
self-contained HTML file to `site/dist/playground/index.html`.

The browser tool intentionally accepts µDewy only. The eventual Dewy
playground can reuse this route once a Dewy compiler can be shipped to the
browser.
