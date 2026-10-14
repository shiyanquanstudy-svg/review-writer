import time
import json
import xml.etree.ElementTree as ET
import requests
from src.config import NCBI_API_KEY, NCBI_EMAIL
from src.schemas import SourceRecord

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# 速率限制：无 key 3次/秒，有 key 10次/秒
_RATE_LIMIT = 0.1 if NCBI_API_KEY else 0.34
_last_request_time = 0.0


def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _RATE_LIMIT:
        time.sleep(_RATE_LIMIT - elapsed)
    _last_request_time = time.time()


def _base_params() -> dict:
    params = {"tool": "review-writer", "email": NCBI_EMAIL or "unknown@example.com"}
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    return params


def esearch(keywords: str, max_results: int = 20,
            mindate: str = None, maxdate: str = None,
            datetype: str = "pdat", sort: str = "relevance") -> list[str]:
    """搜索 PubMed，返回 PMID 列表。
    datetype: pdat(出版日期) / edat(Entrez入库日期)
    sort: relevance / pub_date
    """
    _rate_limit()
    params = _base_params()
    params.update({
        "db": "pubmed",
        "term": keywords,
        "retmax": max_results,
        "retmode": "json",
        "sort": sort,
    })
    if mindate and maxdate:
        params.update({"datetype": datetype, "mindate": mindate, "maxdate": maxdate})

    resp = requests.get(f"{EUTILS_BASE}esearch.fcgi", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("esearchresult", {}).get("idlist", [])


def efetch(pmids: list[str]) -> list[dict]:
    """根据 PMID 列表抓取文章详情，返回 SourceRecord 字典列表。"""
    if not pmids:
        return []
    _rate_limit()
    params = _base_params()
    params.update({
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    })
    resp = requests.get(f"{EUTILS_BASE}efetch.fcgi", params=params, timeout=60)
    resp.raise_for_status()
    return _parse_pubmed_xml(resp.text)


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    """解析 PubMed efetch XML，提取结构化字段。"""
    root = ET.fromstring(xml_text)
    records = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article, ".//PMID")
        title = _text(article, ".//ArticleTitle")
        journal = _text(article, ".//Journal/Title")
        year = _text(article, ".//JournalIssue/PubDate/Year") or \
               _text(article, ".//JournalIssue/PubDate/MedlineDate")

        # 作者
        authors = []
        for a in article.findall(".//AuthorList/Author"):
            last = _text(a, "LastName")
            fore = _text(a, "ForeName")
            if last:
                authors.append(f"{last} {fore}".strip())

        # 摘要（可能有多段）
        abstract_parts = []
        for ab in article.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            text = "".join(ab.itertext()).strip()
            if text:
                abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(abstract_parts)

        # DOI
        doi = None
        for aid in article.findall(".//ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text
                break

        record = SourceRecord(
            source_id=f"pubmed_{pmid}",
            source_type="journal_article",
            title=title or "",
            authors=authors[:10],
            journal=journal,
            year=int(year[:4]) if year and year[:4].isdigit() else None,
            doi=doi,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            abstract=abstract or None,
        )
        records.append(record.model_dump())
    return records


def _text(element, path: str) -> str:
    """安全提取 XML 文本。"""
    node = element.find(path)
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def search_and_fetch(keywords: str, max_results: int = 20,
                     mindate: str = None, maxdate: str = None) -> list[dict]:
    """一步完成搜索 + 抓取。"""
    pmids = esearch(keywords, max_results, mindate, maxdate)
    if not pmids:
        return []
    return efetch(pmids)


if __name__ == "__main__":
    import json
    results = search_and_fetch(
        '"SNDRI"[Title/Abstract] AND "antidepressant"[Title/Abstract]',
        max_results=3,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))