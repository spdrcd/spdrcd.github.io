# spdrcd.github.io

Personal homepage and portfolio for **Chieh "Jack" Chen** — backend software engineer, Houston, TX.

Live at **[chiehc.com](https://chiehc.com)**, served by GitHub Pages from the `master` branch.

## What's here

A single-page site covering:

- **About** — background, languages, and how I got into backend work
- **日本語 · 中文** — the same profile in Japanese and Traditional Chinese
- **Skills & Tooling** — programming languages, backend architecture, workflow
- **Resume** — education and professional experience
- **Community & Leadership** — Houston Nihongo Kai, Code4YALL, TJCC Houston
- **Beyond Work** — the non-engineering half
- **Through the Lens** — travel photography

## Stack

Static HTML, no build step.

| Piece | What it does |
| --- | --- |
| [Bootstrap 5.1](https://getbootstrap.com/) | Layout and utility classes (`css/styles.css`) |
| [Boxicons](https://boxicons.com/) | Social icons in the header |
| [Bootstrap Icons](https://icons.getbootstrap.com/) | Icon set |
| GitHub Pages | Hosting, with `CNAME` pointing at chiehc.com |

## Layout

```
.
├── index.html      # the whole page
├── CNAME           # custom domain for GitHub Pages
├── assets/
│   ├── photos/     # gallery images (1200px, ~150KB each)
│   └── vendor/     # boxicons, bootstrap-icons
├── css/            # styles.css (Bootstrap + theme overrides)
└── js/             # scripts.js
```

## Running it locally

No dependencies. Clone and serve the directory:

```bash
git clone https://github.com/spdrcd/spdrcd.github.io.git
cd spdrcd.github.io
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

Opening `index.html` directly in a browser also works, though relative asset paths behave more predictably over HTTP.

## Deploying

Push to `master`. GitHub Pages rebuilds automatically; changes are usually live within a minute.

## Contact

- **Web** — [chiehc.com](https://chiehc.com)
- **LinkedIn** — [chiehjchen](https://www.linkedin.com/in/chiehjchen/)
- **GitHub** — [@spdrcd](https://github.com/spdrcd)
