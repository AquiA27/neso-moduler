import os
import shutil

files_to_delete = [
    "backend_output.txt",
    "backend_output2.txt",
    "err.log",
    "git_output.txt",
    "git_push_log.txt",
    "git_push_log2.txt",
    "nul",
    "run_test.ps1",
    "run_test2.ps1",
    "run_test3.ps1",
    "quick_test.ps1",
    "check_tenants.py"
]

# Find the weird database file dynamically
for f in os.listdir("."):
    if "backup_old_database.sql" in f:
        files_to_delete.append(f)

backend_files = [
    "=1.0.0",
    "test_api_key.py",
    "test_app.py",
    "test_import.py",
    "check_users.py",
    "add_sample_menu.py",
    "create_relax_payment.py",
    "migrate_data.py",
    "create_test_user.py",
    "create_views.py",
    "fix_relax_admin_tenant.py",
    "generate_embeddings.py",
    "init_db_and_migrate.py"
]

for f in backend_files:
    files_to_delete.append(os.path.join("backend", f))

dirs_to_delete = [
    "super-admin-panel",
    os.path.join("backend", "super-admin-panel")
]

for f in files_to_delete:
    if os.path.exists(f):
        try:
            os.remove(f)
            print("Deleted a file")
        except Exception as e:
            print("Error deleting file")

for d in dirs_to_delete:
    if os.path.exists(d):
        try:
            shutil.rmtree(d, ignore_errors=True)
            print("Deleted directory")
        except Exception as e:
            print("Error deleting dir")
