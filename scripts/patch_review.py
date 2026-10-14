import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

REVIEW = Path(__file__).resolve().parent.parent / "data" / "review_output.md"


def main():
    text = REVIEW.read_text(encoding="utf-8")

    old1 = ("此外，冷冻电镜结构指导合理设计被提出作为未来方向，"
            "但需注意，该方向在本次检索的A类证据中尚无针对核心实体的具体研究数据公开发表，"
            "相关机制与临床前证据仍待补充。")
    new1 = ("此外，冷冻电镜结构指导合理设计被视为未来方向；"
            "[18F]MK-6240 的 2.31 Å 结构与 PI-2620 的结合位点解析已初步展现其潜力（见第 2 节），"
            "但其向新一代示踪剂的转化仍有待验证。")

    old2 = ("需要指出的是，上述证据缺口主要体现为标准化协议与多中心验证数据的不足，"
            "而非临床注册信息的缺失——[18F]flortaucipir已获FDA临床批准[pubmed_33353724]，"
            "属于已有临床注册信息的证据类型，二者应予以区分。")

    # Fix 1
    if old1 in text:
        text = text.replace(old1, new1)
        print("[Fix 1] exact match applied")
    else:
        m = re.search(r"此外，冷冻电镜.{0,180}仍待补充。", text)
        if m:
            text = text[:m.start()] + new1 + text[m.end():]
            print("[Fix 1] regex match applied")
        else:
            print("[Fix 1] NOT FOUND - manual check needed")

    # Fix 2
    if old2 in text:
        text = text.replace(old2, "")
        print("[Fix 2] exact match applied")
    else:
        m = re.search(r"需要指出的是，上述证据缺口.{0,250}二者应予以区分。", text)
        if m:
            text = text[:m.start()] + text[m.end():]
            print("[Fix 2] regex match applied")
        else:
            print("[Fix 2] NOT FOUND - manual check needed")

    REVIEW.write_text(text, encoding="utf-8")
    print("Saved: {0}".format(REVIEW))


if __name__ == "__main__":
    main()