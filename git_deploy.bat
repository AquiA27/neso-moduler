git config --global user.email "alibugra@example.com"
git config --global user.name "Ali Bugra"
git add backend/alembic/versions/2026_03_01_0000-add_missing_indexes_from_report.py
git add super-admin-panel/src/pages/DashboardPage.tsx
git commit -m "feat: add db indexes and super-admin panel UI improvements"
git push > git_output.txt 2>&1
git status >> git_output.txt 2>&1
