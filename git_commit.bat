cd c:\Users\alibu\NesoModuler
git add "frontend-modern/src/components/Layout.tsx" "frontend-modern/src/assets/neso-logo.svg" "frontend-modern/src/pages/LoginPage.tsx" "backend/app/routers/customization_helper.py"
git commit -m "fix(customization): resolve 500 error and update main logo to Neso"
git push > git_push_log.txt 2>&1
git status >> git_push_log.txt 2>&1
