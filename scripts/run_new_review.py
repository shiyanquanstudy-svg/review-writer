import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from src.agents.parse_instruction import parse_instruction
from src.db.db_helper import init_db, save_spec

# =============================================================
# 修改这里：输入新的综述指令
# =============================================================
INSTRUCTION = """
帮我撰写一个综述，阿尔茨海默病 tau 蛋白 PET 显像剂近十年的发展。
摘要主要从阿尔茨海默病的全球负担、tau 蛋白在病理中的作用、
PET 显像剂的主要化学类别、以及第二代 tau 显像剂的临床价值展开。
1 引言介绍阿尔茨海默病和 tau PET 的基本情况。
2 tau 显像剂的化学发展与分类。
3 主要 tau PET 显像剂的临床验证历程。
4 当前挑战与未来方向。
"""
# =============================================================


if __name__ == "__main__":
    init_db()
    spec = parse_instruction(INSTRUCTION)
    rid = save_spec(INSTRUCTION, spec.model_dump())
    print("Saved spec id={0}".format(rid))
    print(json.dumps(spec.model_dump(), ensure_ascii=False, indent=2))