# Y2S2-DBMS 项目拉取与运行说明

最新可运行版本在分支：

```text
scallion-doctor-pharmacist
```

不要只拉取 `main`，因为最新医生端、药剂师端和数据库 dump 都在这个分支里。

---

## 1. 安装 Git

先确认电脑有没有 Git。

打开 PowerShell 或 VSCode Terminal，输入：

```powershell
git --version
```

如果显示版本号，例如：

```text
git version 2.xx.x
```

说明已经安装好了。

如果提示找不到 `git`，需要先安装 Git：

```text
https://git-scm.com/downloads
```

安装时一路 Next 即可。

---

## 2. 打开 VSCode

在电脑上找一个想放项目的文件夹，例如：

```text
Desktop
```

然后在 VSCode 里打开终端：

```text
Terminal → New Terminal
```

---

## 3. Clone 项目

在终端输入：

```powershell
cd Desktop
git clone https://github.com/XUJingcong1/Y2S2-DBMS.git
cd Y2S2-DBMS
```

如果仓库是 private，GitHub 可能会弹出登录页面，登录你的 GitHub 账号即可。

---

## 4. 切换到最新分支

```powershell
git fetch origin
git switch -c scallion-doctor-pharmacist origin/scallion-doctor-pharmacist
```

如果这一步成功，终端会显示你已经在：

```text
scallion-doctor-pharmacist
```

---

## 5. 确认文件已经是最新

```powershell
git status
```

正常应该看到类似：

```text
On branch scallion-doctor-pharmacist
Your branch is up to date with 'origin/scallion-doctor-pharmacist'.
nothing to commit, working tree clean
```

这样就说明代码已经拉下来了。

---

# 拉下来之后怎么运行项目

## 1. 创建虚拟环境

```powershell
python -m venv .venv
```

---

## 2. 激活虚拟环境

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

看到终端前面出现：

```text
(.venv)
```

说明激活成功。

---

## 3. 安装依赖

```powershell
pip install Django PyMySQL cryptography
```

---

## 4. 导入数据库

先确保已经安装并启动 MySQL。

如果数据库还没创建，先运行：

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p -e "DROP DATABASE IF EXISTS hospital_pharmacy_management; CREATE DATABASE hospital_pharmacy_management CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
```

然后在项目文件夹里导入 `.sql` 文件：

```powershell
cmd /c '"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p hospital_pharmacy_management < "hospital_pharmacy_management.sql"'
```

输入 MySQL 密码后等待导入完成。

---

## 5. 检查 Django

```powershell
python manage.py check
```

如果显示：

```text
System check identified no issues
```

说明项目检查通过。

---

## 6. 启动网站

```powershell
python manage.py runserver
```

浏览器打开：

```text
http://127.0.0.1:8000/
```

---

# 测试账号

## Admin

```text
Username: AD-001
Password: admin123
```

## Doctor / Pharmacist / Distributor

可以在 MySQL 里查询测试账号：

```sql
SELECT dc_ID, dc_password FROM doctor LIMIT 5;
SELECT ph_ID, ph_password FROM pharmacist LIMIT 5;
SELECT d_ID, d_password FROM distributor LIMIT 5;
```

---

# 最重要的一句话

请拉取这个分支：

```text
scallion-doctor-pharmacist
```

不要只使用 `main`，因为最新医生端、药剂师端和数据库 dump 都在这个分支里。
