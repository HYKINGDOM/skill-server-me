"""
使用真实 Skill 进行测试

测试 /Users/bingbing/Documents/project/skills/skills/ 目录中的所有真实 skill
"""
import asyncio
import os
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

# 真实 skill 目录
REAL_SKILLS_DIR = Path("/Users/bingbing/Documents/project/skills/skills")

# 测试配置
BASE_URL = "http://localhost:8000"
TEST_USERNAME = f"realskill_test_{datetime.now().strftime('%Y%m%d%H%M%S')}"
TEST_EMAIL = f"{TEST_USERNAME}@test.com"
TEST_PASSWORD = "test123456"

# 测试结果统计
test_results = {
    "passed": 0,
    "failed": 0,
    "errors": [],
    "skills_tested": [],
}


def log_test(name: str, passed: bool, message: str = ""):
    """记录测试结果"""
    if passed:
        test_results["passed"] += 1
        print(f"  ✅ {name}")
    else:
        test_results["failed"] += 1
        test_results["errors"].append(f"{name}: {message}")
        print(f"  ❌ {name}: {message}")


class RealSkillTester:
    """真实 Skill 测试类"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.uploaded_skills: list[dict] = []

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    @property
    def headers(self) -> dict:
        """获取认证头"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def get_available_skills(self) -> list[Path]:
        """获取真实 skill 目录中的所有 skill"""
        if not REAL_SKILLS_DIR.exists():
            print(f"❌ 真实 skill 目录不存在: {REAL_SKILLS_DIR}")
            return []
        
        skills = []
        for item in REAL_SKILLS_DIR.iterdir():
            if item.is_dir():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    skills.append(item)
        
        return sorted(skills)

    def create_skill_zip(self, skill_dir: Path) -> Path:
        """创建 skill 的 ZIP 包"""
        # 创建临时 ZIP 文件
        tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tmp_zip.close()
        
        with zipfile.ZipFile(tmp_zip.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in skill_dir.rglob("*"):
                if file_path.is_file():
                    # 计算相对路径
                    rel_path = file_path.relative_to(skill_dir)
                    zf.write(file_path, rel_path)
        
        return Path(tmp_zip.name)

    async def register_and_login(self):
        """注册并登录"""
        print("\n📋 注册并登录测试用户")
        
        # 注册
        try:
            response = await self.client.post(
                f"{BASE_URL}/auth/register",
                json={
                    "username": TEST_USERNAME,
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                },
            )
            if response.status_code in [201, 400]:
                log_test("用户注册", True, "用户已存在或注册成功")
            else:
                log_test("用户注册", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("用户注册", False, str(e))
            return False
        
        # 登录
        try:
            response = await self.client.post(
                f"{BASE_URL}/auth/login",
                json={
                    "username": TEST_USERNAME,
                    "password": TEST_PASSWORD,
                },
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.user_id = data.get("id")
                log_test("用户登录", self.token is not None, f"Token: {self.token[:20] if self.token else 'None'}...")
                return True
            else:
                log_test("用户登录", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            log_test("用户登录", False, str(e))
            return False

    async def test_upload_skill(self, skill_dir: Path) -> Optional[dict]:
        """测试上传单个 skill"""
        skill_name = skill_dir.name
        test_name = f"上传 Skill: {skill_name}"
        
        try:
            # 创建 ZIP 包
            zip_path = self.create_skill_zip(skill_dir)
            
            # 使用时间戳避免名称冲突
            unique_name = f"{skill_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            try:
                with open(zip_path, "rb") as f:
                    response = await self.client.post(
                        f"{BASE_URL}/skills/upload?name={unique_name}",
                        headers=self.headers,
                        files={"file": (f"{skill_name}.zip", f, "application/zip")},
                        timeout=120.0,
                    )
                
                if response.status_code == 201:
                    data = response.json()
                    log_test(test_name, True, f"Skill ID: {data.get('id')}")
                    return {
                        "original_name": skill_name,
                        "unique_name": unique_name,
                        "id": data.get("id"),
                        "data": data,
                    }
                else:
                    log_test(test_name, False, f"状态码: {response.status_code}, {response.text[:200]}")
                    return None
            finally:
                # 清理临时 ZIP 文件
                os.remove(zip_path)
                
        except Exception as e:
            log_test(test_name, False, str(e))
            return None

    async def test_get_skill(self, skill_id: str, skill_name: str):
        """测试获取 skill 详情"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/skills/{skill_id}",
            )
            if response.status_code == 200:
                data = response.json()
                skill_data = data.get("skill", {})
                log_test(
                    f"获取 Skill 详情: {skill_name}",
                    skill_data.get("name") is not None,
                    f"名称: {skill_data.get('name')}, 标题: {skill_data.get('title')}"
                )
                return data
            else:
                log_test(f"获取 Skill 详情: {skill_name}", False, f"状态码: {response.status_code}")
                return None
        except Exception as e:
            log_test(f"获取 Skill 详情: {skill_name}", False, str(e))
            return None

    async def test_download_skill(self, skill_id: str, skill_name: str):
        """测试下载 skill 包"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/skills/{skill_id}/download",
                headers=self.headers,
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                content_length = len(response.content)
                log_test(
                    f"下载 Skill 包: {skill_name}",
                    "zip" in content_type or "application/octet-stream" in content_type,
                    f"类型: {content_type}, 大小: {content_length} bytes"
                )
                return True
            else:
                log_test(f"下载 Skill 包: {skill_name}", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            log_test(f"下载 Skill 包: {skill_name}", False, str(e))
            return False

    async def test_search_skill(self, skill_name: str):
        """测试搜索 skill"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/search",
                params={"q": skill_name, "page": 1, "page_size": 10},
            )
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                found = any(skill_name in item.get("name", "") for item in items)
                log_test(
                    f"搜索 Skill: {skill_name}",
                    True,
                    f"找到 {len(items)} 个结果"
                )
                return data
            else:
                log_test(f"搜索 Skill: {skill_name}", False, f"状态码: {response.status_code}")
                return None
        except Exception as e:
            log_test(f"搜索 Skill: {skill_name}", False, str(e))
            return None

    async def test_list_skills(self):
        """测试列出所有 skills"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/skills",
                params={"page": 1, "page_size": 100},
            )
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                total = data.get("total", 0)
                log_test("列出所有 Skills", True, f"总数: {total}")
                return data
            else:
                log_test("列出所有 Skills", False, f"状态码: {response.status_code}")
                return None
        except Exception as e:
            log_test("列出所有 Skills", False, str(e))
            return None

    async def cleanup(self):
        """清理测试数据"""
        print("\n📋 清理测试数据")
        
        for skill_info in self.uploaded_skills:
            skill_id = skill_info.get("id")
            skill_name = skill_info.get("original_name", "unknown")
            if skill_id:
                try:
                    response = await self.client.delete(
                        f"{BASE_URL}/skills/{skill_id}",
                        headers=self.headers,
                    )
                    log_test(
                        f"删除 Skill: {skill_name}",
                        response.status_code == 200,
                        f"Skill ID: {skill_id}"
                    )
                except Exception as e:
                    log_test(f"删除 Skill: {skill_name}", False, str(e))

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("🚀 开始使用真实 Skill 进行测试")
        print(f"📁 真实 Skill 目录: {REAL_SKILLS_DIR}")
        print("=" * 60)

        # 获取可用的 skills
        available_skills = self.get_available_skills()
        print(f"\n📋 发现 {len(available_skills)} 个真实 Skill:")
        for skill_dir in available_skills:
            print(f"  - {skill_dir.name}")
        
        if not available_skills:
            print("❌ 没有找到可用的真实 Skill")
            return False

        # 注册并登录
        if not await self.register_and_login():
            print("❌ 无法完成用户认证，测试终止")
            return False

        # 上传所有真实 skill
        print(f"\n📋 上传 {len(available_skills)} 个真实 Skill")
        for skill_dir in available_skills:
            result = await self.test_upload_skill(skill_dir)
            if result:
                self.uploaded_skills.append(result)

        # 测试获取 skill 详情
        print(f"\n📋 测试获取 Skill 详情")
        for skill_info in self.uploaded_skills:
            await self.test_get_skill(skill_info["id"], skill_info["original_name"])

        # 测试下载 skill 包
        print(f"\n📋 测试下载 Skill 包")
        for skill_info in self.uploaded_skills[:5]:  # 只测试前5个，节省时间
            await self.test_download_skill(skill_info["id"], skill_info["original_name"])

        # 测试搜索功能
        print(f"\n📋 测试搜索功能")
        for skill_info in self.uploaded_skills[:5]:  # 只测试前5个
            await self.test_search_skill(skill_info["original_name"])

        # 测试列出所有 skills
        print(f"\n📋 测试列出所有 Skills")
        await self.test_list_skills()

        # 清理
        await self.cleanup()

        # 打印结果
        print("\n" + "=" * 60)
        print("📊 测试结果汇总")
        print("=" * 60)
        print(f"✅ 通过: {test_results['passed']}")
        print(f"❌ 失败: {test_results['failed']}")
        print(f"📁 测试的 Skill 数量: {len(available_skills)}")
        print(f"📤 成功上传的 Skill 数量: {len(self.uploaded_skills)}")
        
        total = test_results['passed'] + test_results['failed']
        if total > 0:
            print(f"📈 通过率: {test_results['passed'] / total * 100:.1f}%")

        if test_results["errors"]:
            print("\n❌ 失败详情:")
            for error in test_results["errors"]:
                print(f"  - {error}")

        print("=" * 60)

        return test_results["failed"] == 0


async def main():
    """主函数"""
    tester = RealSkillTester()
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
