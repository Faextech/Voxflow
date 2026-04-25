import re
import os

with open("app/templates/dashboard.html", "r") as f:
    html = f.read()

# 1. Add Lucide script to head
if "lucide" not in html:
    html = html.replace("</head>", '    <script src="https://unpkg.com/lucide@latest"></script>\n</head>')

# 2. Add lucide.createIcons() to JS onload
if "lucide.createIcons()" not in html:
    html = html.replace("window.addEventListener('DOMContentLoaded', () => {", "window.addEventListener('DOMContentLoaded', () => {\n            if (window.lucide) lucide.createIcons();")
    html = html.replace("window.addEventListener('load', nexusAutoInit);", "window.addEventListener('load', nexusAutoInit);\n    window.addEventListener('load', () => { if (window.lucide) lucide.createIcons(); });")

# We will just write the changes out to check them
with open("app/templates/dashboard.html", "w") as f:
    f.write(html)
print("Lucide injected")
