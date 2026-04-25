import re

with open('app/templates/dashboard.html', 'r') as f:
    html = f.read()

old_script = """        if (localStorage.getItem('nexdial_theme') !== 'dark') {
            document.body.classList.add('light-mode');
        }
        function toggleTheme() {
            const cb = document.getElementById('themeCheckbox');
            if (cb) {
                if (cb.checked) {
                    document.body.classList.add('light-mode');
                    localStorage.setItem('nexdial_theme', 'light');
                } else {
                    document.body.classList.remove('light-mode');
                    localStorage.setItem('nexdial_theme', 'dark');
                }
            }
        }
        window.addEventListener('DOMContentLoaded', () => {
            const cb = document.getElementById('themeCheckbox');
            if (cb) {
                cb.checked = document.body.classList.contains('light-mode');
            }
        });"""

new_script = """        if (localStorage.getItem('nexdial_theme') === 'dark') {
            document.documentElement.classList.add('dark');
        }
        function toggleTheme() {
            const cb = document.getElementById('themeCheckbox');
            if (cb) {
                if (cb.checked) {
                    document.documentElement.classList.add('dark');
                    localStorage.setItem('nexdial_theme', 'dark');
                } else {
                    document.documentElement.classList.remove('dark');
                    localStorage.setItem('nexdial_theme', 'light');
                }
            }
        }
        window.addEventListener('DOMContentLoaded', () => {
            const cb = document.getElementById('themeCheckbox');
            if (cb) {
                cb.checked = document.documentElement.classList.contains('dark');
            }
        });"""

html = html.replace(old_script, new_script)

with open('app/templates/dashboard.html', 'w') as f:
    f.write(html)
print("Theme JS fixed")
