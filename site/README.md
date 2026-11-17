# site/

Landing page served at <https://jaylabb.my.id/openlinko/> (English) and `/openlinko/id/`
(Indonesian). Plain static files, no framework.

- `build.py` holds the page template and both languages' copy; run `python site/build.py` to
  regenerate `openlinko/index.html` and `openlinko/id/index.html`. Edit copy there, not in the HTML.
- `openlinko/assets/` has the CSS and the small script (byte-dump hero, install tabs, reveals).
  The hero's 73-byte frame is a sample, but every offset it highlights is the real one from
  `docs/api-map.md`.
- Screenshots in `openlinko/img/` are copies of `docs/screenshots/v2-*-light.jpg`.

Deploy: zip the changed files, upload to `public_html` on the jaylabb.my.id host and unzip. Hestia's
unzip does not overwrite, so delete the old copies first. The sitemap (`openlinko/sitemap.xml`) is
submitted in Google Search Console under the jaylabb.my.id property.
