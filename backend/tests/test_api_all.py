"""
API接口全面测试脚本

测试所有API接口，验证返回结果符合预期
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

# 测试配置
BASE_URL = "http://localhost:8000"
TEST_USERNAME = f"apitest_{datetime.now().strftime('%Y%m%d%H%M%S')}"
TEST_EMAIL = f"{TEST_USERNAME}@test.com"
TEST_PASSWORD = "test123456"

# 测试结果统计
test_results = {
    "passed": 0,
    "failed": 0,
    "errors": [],
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


class APITester:
    """API测试类"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.token: Optional[str] = None
        self.refresh_token_value: Optional[str] = None
        self.user_id: Optional[str] = None
        self.skill_id: Optional[str] = None
        self.repo_id: Optional[str] = None
        self.notification_id: Optional[str] = None

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    @property
    def headers(self) -> dict:
        """获取认证头"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    # ==================== 系统接口测试 ====================

    async def test_health(self):
        """测试健康检查接口"""
        print("\n📋 测试系统接口")
        try:
            response = await self.client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                data = response.json()
                log_test("健康检查", data.get("status") == "healthy", str(data))
            else:
                log_test("健康检查", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("健康检查", False, str(e))

    async def test_root(self):
        """测试根路径"""
        try:
            response = await self.client.get(f"{BASE_URL}/")
            if response.status_code == 200:
                data = response.json()
                log_test("根路径", "name" in data and "version" in data, str(data))
            else:
                log_test("根路径", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("根路径", False, str(e))

    # ==================== 认证接口测试 ====================

    async def test_register(self):
        """测试用户注册"""
        print("\n📋 测试认证接口")
        try:
            response = await self.client.post(
                f"{BASE_URL}/auth/register",
                json={
                    "username": TEST_USERNAME,
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                },
            )
            if response.status_code == 201:
                data = response.json()
                self.user_id = data.get("id")
                log_test("用户注册", True, f"用户ID: {self.user_id}")
            elif response.status_code == 400:
                # 用户已存在，尝试登录
                log_test("用户注册", True, "用户已存在，将使用登录")
            else:
                log_test("用户注册", False, f"状态码: {response.status_code}, {response.text}")
        except Exception as e:
            log_test("用户注册", False, str(e))

    async def test_login(self):
        """测试用户登录"""
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
                self.refresh_token_value = data.get("refresh_token")
                log_test("用户登录", self.token is not None, f"Token: {self.token[:20]}...")
            else:
                log_test("用户登录", False, f"状态码: {response.status_code}, {response.text}")
        except Exception as e:
            log_test("用户登录", False, str(e))

    async def test_get_current_user(self):
        """测试获取当前用户信息"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/auth/me",
                headers=self.headers,
            )
            if response.status_code == 200:
                data = response.json()
                log_test("获取当前用户", data.get("username") == TEST_USERNAME, str(data))
            else:
                log_test("获取当前用户", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("获取当前用户", False, str(e))

    async def test_refresh_token(self):
        """测试刷新令牌"""
        if not self.refresh_token_value:
            log_test("刷新令牌", False, "未登录")
            return
        try:
            response = await self.client.post(
                f"{BASE_URL}/auth/refresh",
                params={"refresh_token": self.refresh_token_value},
            )
            if response.status_code == 200:
                data = response.json()
                new_token = data.get("access_token")
                log_test("刷新令牌", new_token is not None, "获取新令牌成功")
            else:
                log_test("刷新令牌", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("刷新令牌", False, str(e))

    async def test_change_password(self):
        """测试修改密码"""
        try:
            response = await self.client.post(
                f"{BASE_URL}/auth/change-password",
                headers=self.headers,
                json={
                    "old_password": TEST_PASSWORD,
                    "new_password": TEST_PASSWORD,
                },
            )
            if response.status_code == 200:
                log_test("修改密码", True, "密码修改成功")
            else:
                log_test("修改密码", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("修改密码", False, str(e))

    # ==================== Skill接口测试 ====================

    async def test_create_skill(self):
        """测试创建Skill"""
        print("\n📋 测试Skill接口")
        try:
            response = await self.client.post(
                f"{BASE_URL}/skills",
                headers=self.headers,
                json={
                    "name": f"test-skill-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "skill_md_content": "# Test Skill\n\nThis is a test skill.",
                },
            )
            if response.status_code == 201:
                data = response.json()
                self.skill_id = data.get("id")
                log_test("创建Skill", True, f"Skill ID: {self.skill_id}")
            else:
                log_test("创建Skill", False, f"状态码: {response.status_code}, {response.text}")
        except Exception as e:
            log_test("创建Skill", False, str(e))

    async def test_upload_skill(self):
        """测试上传ZIP包创建Skill"""
        # 创建临时ZIP文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name

        with zipfile.ZipFile(tmp_path, "w") as zf:
            zf.writestr("SKILL.md", "# Uploaded Skill\n\nThis is an uploaded skill.")

        try:
            skill_name = f"uploaded-skill-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            with open(tmp_path, "rb") as f:
                response = await self.client.post(
                    f"{BASE_URL}/skills/upload?name={skill_name}",
                    headers=self.headers,
                    files={"file": ("uploaded-skill.zip", f, "application/zip")},
                )
            if response.status_code == 201:
                data = response.json()
                log_test("上传ZIP创建Skill", True, f"Skill ID: {data.get('id')}")
            else:
                log_test("上传ZIP创建Skill", False, f"状态码: {response.status_code}, {response.text}")
        except Exception as e:
            log_test("上传ZIP创建Skill", False, str(e))
        finally:
            os.remove(tmp_path)

    async def test_list_skills(self):
        """测试列出Skills"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/skills",
                params={"page": 1, "page_size": 10},
            )
            if response.status_code == 200:
                data = response.json()
                log_test("列出Skills", "items" in data and "total" in data, f"总数: {data.get('total')}")
            else:
                log_test("列出Skills", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("列出Skills", False, str(e))

    async def test_get_skill(self):
        """测试获取Skill详情"""
        if not self.skill_id:
            log_test("获取Skill详情", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.get(
                f"{BASE_URL}/skills/{self.skill_id}",
            )
            if response.status_code == 200:
                data = response.json()
                log_test("获取Skill详情", "skill" in data, f"Skill名称: {data.get('skill', {}).get('name')}")
            else:
                log_test("获取Skill详情", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("获取Skill详情", False, str(e))

    async def test_update_skill(self):
        """测试更新Skill"""
        if not self.skill_id:
            log_test("更新Skill", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.put(
                f"{BASE_URL}/skills/{self.skill_id}",
                headers=self.headers,
                json={"skill_md_content": "# Updated Skill\n\nThis skill has been updated."},
            )
            if response.status_code == 200:
                log_test("更新Skill", True, "更新成功")
            else:
                log_test("更新Skill", False, f"状态码: {response.status_code}, {response.text}")
        except Exception as e:
            log_test("更新Skill", False, str(e))

    async def test_acquire_lock(self):
        """测试获取编辑锁"""
        if not self.skill_id:
            log_test("获取编辑锁", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.post(
                f"{BASE_URL}/skills/{self.skill_id}/lock",
                headers=self.headers,
            )
            if response.status_code == 200:
                data = response.json()
                log_test("获取编辑锁", data.get("is_locked") == True, str(data))
            else:
                log_test("获取编辑锁", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("获取编辑锁", False, str(e))

    async def test_release_lock(self):
        """测试释放编辑锁"""
        if not self.skill_id:
            log_test("释放编辑锁", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.delete(
                f"{BASE_URL}/skills/{self.skill_id}/lock",
                headers=self.headers,
            )
            if response.status_code == 200:
                data = response.json()
                log_test("释放编辑锁", data.get("is_locked") == False, str(data))
            else:
                log_test("释放编辑锁", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("释放编辑锁", False, str(e))

    async def test_download_skill(self):
        """测试下载Skill包"""
        if not self.skill_id:
            log_test("下载Skill包", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.get(
                f"{BASE_URL}/skills/{self.skill_id}/download",
                headers=self.headers,
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                log_test("下载Skill包", "zip" in content_type or "application/octet-stream" in content_type, f"类型: {content_type}")
            else:
                log_test("下载Skill包", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("下载Skill包", False, str(e))

    # ==================== 收藏接口测试 ====================

    async def test_add_favorite(self):
        """测试添加收藏"""
        print("\n📋 测试收藏接口")
        if not self.skill_id:
            log_test("添加收藏", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.post(
                f"{BASE_URL}/favorites/{self.skill_id}",
                headers=self.headers,
            )
            if response.status_code == 200:
                log_test("添加收藏", True, "收藏成功")
            else:
                log_test("添加收藏", False, f"状态码: {response.status_code}, {response.text}")
        except Exception as e:
            log_test("添加收藏", False, str(e))

    async def test_list_favorites(self):
        """测试列出收藏"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/favorites",
                headers=self.headers,
            )
            if response.status_code == 200:
                data = response.json()
                log_test("列出收藏", "items" in data, f"总数: {data.get('total')}")
            else:
                log_test("列出收藏", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("列出收藏", False, str(e))

    async def test_check_favorite(self):
        """测试检查是否已收藏"""
        if not self.skill_id:
            log_test("检查收藏状态", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.get(
                f"{BASE_URL}/favorites/check/{self.skill_id}",
                headers=self.headers,
            )
            if response.status_code == 200:
                data = response.json()
                log_test("检查收藏状态", "is_favorited" in data, str(data))
            else:
                log_test("检查收藏状态", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("检查收藏状态", False, str(e))

    async def test_remove_favorite(self):
        """测试取消收藏"""
        if not self.skill_id:
            log_test("取消收藏", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.delete(
                f"{BASE_URL}/favorites/{self.skill_id}",
                headers=self.headers,
            )
            if response.status_code == 200:
                log_test("取消收藏", True, "取消成功")
            else:
                log_test("取消收藏", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("取消收藏", False, str(e))

    # ==================== 通知接口测试 ====================

    async def test_list_notifications(self):
        """测试列出通知"""
        print("\n📋 测试通知接口")
        try:
            response = await self.client.get(
                f"{BASE_URL}/notifications",
                headers=self.headers,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("items"):
                    self.notification_id = data["items"][0].get("id")
                log_test("列出通知", "items" in data, f"总数: {data.get('total')}")
            else:
                log_test("列出通知", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("列出通知", False, str(e))

    async def test_unread_count(self):
        """测试获取未读数量"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/notifications/unread-count",
                headers=self.headers,
            )
            if response.status_code == 200:
                data = response.json()
                log_test("未读数量", "unread_count" in data, str(data))
            else:
                log_test("未读数量", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("未读数量", False, str(e))

    async def test_mark_all_read(self):
        """测试标记所有已读"""
        try:
            response = await self.client.post(
                f"{BASE_URL}/notifications/read-all",
                headers=self.headers,
            )
            if response.status_code == 200:
                log_test("标记所有已读", True, "操作成功")
            else:
                log_test("标记所有已读", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("标记所有已读", False, str(e))

    # ==================== 时间线接口测试 ====================

    async def test_skill_timeline(self):
        """测试获取Skill时间线"""
        print("\n📋 测试时间线接口")
        if not self.skill_id:
            log_test("Skill时间线", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.get(
                f"{BASE_URL}/timeline/skill/{self.skill_id}",
            )
            if response.status_code == 200:
                data = response.json()
                log_test("Skill时间线", "items" in data, f"总数: {data.get('total')}")
            else:
                log_test("Skill时间线", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("Skill时间线", False, str(e))

    async def test_recent_events(self):
        """测试获取最近事件"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/timeline/recent",
                params={"limit": 10},
            )
            if response.status_code == 200:
                data = response.json()
                log_test("最近事件", isinstance(data, list), f"数量: {len(data)}")
            else:
                log_test("最近事件", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("最近事件", False, str(e))

    # ==================== 版本接口测试 ====================

    async def test_list_versions(self):
        """测试列出版本"""
        print("\n📋 测试版本接口")
        if not self.skill_id:
            log_test("列出版本", False, "没有可用的Skill ID")
            return
        try:
            response = await self.client.get(
                f"{BASE_URL}/versions/skill/{self.skill_id}",
            )
            if response.status_code == 200:
                data = response.json()
                log_test("列出版本", "items" in data, f"总数: {data.get('total')}")
            else:
                log_test("列出版本", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("列出版本", False, str(e))

    # ==================== 搜索接口测试 ====================

    async def test_search(self):
        """测试搜索"""
        print("\n📋 测试搜索接口")
        try:
            response = await self.client.get(
                f"{BASE_URL}/search",
                params={"q": "test", "page": 1, "page_size": 10},
            )
            if response.status_code == 200:
                data = response.json()
                log_test("搜索", "items" in data and "query" in data, f"查询: {data.get('query')}, 结果: {data.get('total')}")
            else:
                log_test("搜索", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("搜索", False, str(e))

    async def test_rebuild_index(self):
        """测试重建索引"""
        try:
            response = await self.client.post(
                f"{BASE_URL}/search/rebuild-index",
            )
            if response.status_code == 200:
                data = response.json()
                log_test("重建索引", "fulltext_indexed" in data, str(data))
            else:
                log_test("重建索引", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("重建索引", False, str(e))

    # ==================== Git仓库接口测试 ====================

    async def test_list_repos(self):
        """测试列出仓库"""
        print("\n📋 测试Git仓库接口")
        try:
            response = await self.client.get(
                f"{BASE_URL}/repos",
            )
            if response.status_code == 200:
                data = response.json()
                log_test("列出仓库", "items" in data, f"总数: {data.get('total')}")
            else:
                log_test("列出仓库", False, f"状态码: {response.status_code}")
        except Exception as e:
            log_test("列出仓库", False, str(e))

    # ==================== 清理测试数据 ====================

    async def cleanup(self):
        """清理测试数据"""
        print("\n📋 清理测试数据")
        # 删除创建的Skill
        if self.skill_id:
            try:
                response = await self.client.delete(
                    f"{BASE_URL}/skills/{self.skill_id}",
                    headers=self.headers,
                )
                log_test("删除Skill", response.status_code == 200, f"Skill ID: {self.skill_id}")
            except Exception as e:
                log_test("删除Skill", False, str(e))

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("🚀 开始API接口全面测试")
        print("=" * 60)

        # 系统接口
        await self.test_health()
        await self.test_root()

        # 认证接口
        await self.test_register()
        await self.test_login()
        await self.test_get_current_user()
        await self.test_refresh_token()
        await self.test_change_password()

        # Skill接口
        await self.test_create_skill()
        await self.test_upload_skill()
        await self.test_list_skills()
        await self.test_get_skill()
        await self.test_update_skill()
        await self.test_acquire_lock()
        await self.test_release_lock()
        await self.test_download_skill()

        # 收藏接口
        await self.test_add_favorite()
        await self.test_list_favorites()
        await self.test_check_favorite()
        await self.test_remove_favorite()

        # 通知接口
        await self.test_list_notifications()
        await self.test_unread_count()
        await self.test_mark_all_read()

        # 时间线接口
        await self.test_skill_timeline()
        await self.test_recent_events()

        # 版本接口
        await self.test_list_versions()

        # 搜索接口
        await self.test_search()
        await self.test_rebuild_index()

        # Git仓库接口
        await self.test_list_repos()

        # 清理
        await self.cleanup()

        # 打印结果
        print("\n" + "=" * 60)
        print("📊 测试结果汇总")
        print("=" * 60)
        print(f"✅ 通过: {test_results['passed']}")
        print(f"❌ 失败: {test_results['failed']}")
        print(f"📈 通过率: {test_results['passed'] / (test_results['passed'] + test_results['failed']) * 100:.1f}%")

        if test_results["errors"]:
            print("\n❌ 失败详情:")
            for error in test_results["errors"]:
                print(f"  - {error}")

        print("=" * 60)

        return test_results["failed"] == 0


async def main():
    """主函数"""
    tester = APITester()
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
