"""
数据库迁移脚本

添加搜索统计字段到 skills 表：
- download_count: 下载数
- favorite_count: 收藏数
- usage_count: 使用数
- is_official: 是否官方认证
"""
import asyncio
import sqlite3
from pathlib import Path

from app.core.config import get_settings


async def migrate():
    """执行数据库迁移"""
    settings = get_settings()
    
    if settings.database_type != "sqlite":
        print("此迁移脚本仅支持 SQLite 数据库")
        return
    
    db_path = Path(settings.sqlite_db_path)
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(skills)")
        columns = [col[1] for col in cursor.fetchall()]
        
        new_columns = [
            ("download_count", "INTEGER DEFAULT 0"),
            ("favorite_count", "INTEGER DEFAULT 0"),
            ("usage_count", "INTEGER DEFAULT 0"),
            ("is_official", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                print(f"添加列: {col_name}")
                cursor.execute(f"ALTER TABLE skills ADD COLUMN {col_name} {col_type}")
        
        conn.commit()
        print("迁移完成")
        
    except Exception as e:
        print(f"迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
