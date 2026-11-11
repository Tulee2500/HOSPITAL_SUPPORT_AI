"""RAG nâng cấp: Gemini Embedding + FAISS vector store.

Lần đầu chạy: embed tất cả tài liệu → lưu index xuống disk.
Các lần sau: load index từ disk → không gọi API lại, khởi động nhanh.

Fallback: nếu Gemini Embedding gặp lỗi (rate limit, network) thì tự động
          dùng lại TF-IDF ký tự như phiên bản cũ để app không bị sập.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np

# ──────────────────────────────────────────────
# Hằng số cấu hình
# ──────────────────────────────────────────────
DOCS_DIR = Path("data/docs")
INDEX_DIR = Path("data/index")          # thư mục lưu FAISS index + metadata
INDEX_FILE = INDEX_DIR / "faiss.index"
META_FILE  = INDEX_DIR / "chunks.json"
EMBED_MODEL = "gemini-embedding-2"      # model embedding mới nhất của Gemini
CHUNK_SIZE  = 750                        # ký tự mỗi đoạn (tăng để giữ trọn vẹn danh sách/bảng giá)
CHUNK_OVERLAP = 120                      # ký tự chồng lấp giữa 2 đoạn liền kề
TOP_K = 5                                # số đoạn trả về mỗi lần tìm kiếm
MIN_SCORE = 0.0                          # không lọc theo score tuyệt đối — MMR + diversity đủ để lọc


# ──────────────────────────────────────────────
# Tiện ích: chia văn bản thành chunk chồng lấp
# ──────────────────────────────────────────────
def _clean_line(line: str) -> str:
    """Loại bỏ các dòng chỉ là dấu gạch ngang / dấu bằng (separator lines)."""
    stripped = line.strip()
    if stripped and all(c in "=-_* \t" for c in stripped):
        return ""
    return line


def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Chia văn bản thành các đoạn ~chunk_size ký tự, có chồng lấp để không mất ngữ cảnh."""
    # Lọc bỏ dòng separator (======= / -------)
    cleaned_lines = [_clean_line(l) for l in text.splitlines()]
    text = "\n".join(cleaned_lines)

    # Cắt theo đoạn văn (dòng trống)
    paragraphs: list[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        if para:
            paragraphs.append(para)

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > chunk_size:
            chunks.append(current.strip())
            # Lấy phần cuối current làm phần chồng lấp
            current = current[-overlap:] + "\n\n" + para if overlap else para
        else:
            current = (current + "\n\n" + para).strip() if current else para

    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if len(c) > 30]  # loại bỏ chunk quá ngắn


# ──────────────────────────────────────────────
# Lớp chính: Retriever
# ──────────────────────────────────────────────
class Retriever:
    """
    Tìm kiếm ngữ nghĩa (semantic search) dùng Gemini Embedding + FAISS.
    Tự động fallback về TF-IDF nếu không thể dùng embedding.
    """

    def __init__(self, docs_dir: str | Path = DOCS_DIR):
        self.docs_dir = Path(docs_dir)
        self.chunks: list[dict] = []          # [{"text": ..., "source": ...}]
        self._faiss_index = None
        self._tfidf_fallback = None           # dùng khi Gemini Embedding không khả dụng

        self._load_or_build_index()

    # ── Đọc tài liệu ────────────────────────────────────────────────────────
    def _read_docs(self) -> list[dict]:
        """Đọc tất cả file .txt trong docs_dir, trả về list chunk dict."""
        chunks = []
        for path in sorted(self.docs_dir.glob("*.txt")):
            raw = path.read_text(encoding="utf-8")
            lines = raw.splitlines()
            source = path.name
            # Dòng đầu có thể là "NGUON: <tên/link>"
            if lines and lines[0].upper().startswith("NGUON:"):
                source = lines[0].split(":", 1)[1].strip()
                lines = lines[1:]
            body = "\n".join(lines)
            for chunk_text in _split_text(body):
                chunks.append({"text": chunk_text, "source": source})
        if not chunks:
            raise RuntimeError(f"Không tìm thấy file .txt nào trong {self.docs_dir}")
        return chunks

    # ── Gọi Gemini Embedding API ─────────────────────────────────────────────
    @staticmethod
    def _embed_batch(texts: list[str], retries: int = 3) -> np.ndarray | None:
        """
        Embed danh sách văn bản bằng Gemini Embedding API.
        Gọi từng text một (vì gemini-embedding-2 không nhận batch list).
        Trả về numpy array (N, D) hoặc None nếu thất bại.
        """
        try:
            from dotenv import load_dotenv
            load_dotenv()
            from google import genai
            from google.genai import types as gtypes

            client  = genai.Client()
            vectors = []
            total   = len(texts)

            for i, text in enumerate(texts):
                if i % 10 == 0:
                    print(f"[Embedding] {i}/{total}...", flush=True)
                for attempt in range(retries):
                    try:
                        result = client.models.embed_content(
                            model=EMBED_MODEL,
                            contents=text,
                            config=gtypes.EmbedContentConfig(
                                task_type="RETRIEVAL_DOCUMENT",
                            ),
                        )
                        vectors.append(result.embeddings[0].values)
                        break
                    except Exception as err:
                        if attempt < retries - 1 and any(
                            k in str(err) for k in ("429", "503", "UNAVAILABLE", "overloaded")
                        ):
                            wait = 2 ** (attempt + 1)
                            print(f"[Embedding] Bận, thử lại sau {wait}s...")
                            time.sleep(wait)
                        else:
                            raise

            print(f"[Embedding] Hoàn tất {total} chunks.")
            return np.array(vectors, dtype="float32")
        except Exception as e:
            print(f"[Embedding] Lỗi Gemini Embedding: {e}. Chuyển sang TF-IDF.")
            return None

    @staticmethod
    def _embed_query(query: str) -> np.ndarray | None:
        """Embed một câu truy vấn (task_type = RETRIEVAL_QUERY). Trả về (1, D) array."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            from google import genai
            from google.genai import types as gtypes

            client = genai.Client()
            result = client.models.embed_content(
                model=EMBED_MODEL,
                contents=query,          # truyền string, không phải list
                config=gtypes.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
            )
            vec = np.array([result.embeddings[0].values], dtype="float32")
            return vec
        except Exception as e:
            print(f"[Embedding] Lỗi embed query: {e}")
            return None

    # ── Build / Load FAISS index ─────────────────────────────────────────────
    def _build_faiss_index(self, vectors: np.ndarray):
        """Tạo FAISS IndexFlatIP (inner product = cosine nếu vector đã normalize)."""
        import faiss  # noqa: import bên trong để app không crash khi chưa cài

        dim = vectors.shape[1]
        # Normalize để cosine similarity = dot product
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(dim)
        index.add(vectors)
        return index

    def _save_index(self, index) -> None:
        import faiss
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(INDEX_FILE))
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)
        print(f"[Index] Đã lưu {len(self.chunks)} chunk vào {INDEX_DIR}")

    def _load_saved_index(self) -> bool:
        """Load index từ disk. Trả về True nếu thành công."""
        try:
            import faiss
            if not INDEX_FILE.exists() or not META_FILE.exists():
                return False
            # Kiểm tra xem doc có thay đổi không (so sánh số lượng file và mtime)
            if not self._index_is_fresh():
                return False
            self._faiss_index = faiss.read_index(str(INDEX_FILE))
            with open(META_FILE, encoding="utf-8") as f:
                self.chunks = json.load(f)
            print(f"[Index] Load từ cache: {len(self.chunks)} chunk.")
            return True
        except Exception as e:
            print(f"[Index] Không load được cache: {e}. Sẽ build lại.")
            return False

    def _index_is_fresh(self) -> bool:
        """Index còn mới nếu tất cả file .txt đều cũ hơn file index."""
        if not INDEX_FILE.exists():
            return False
        index_mtime = INDEX_FILE.stat().st_mtime
        for txt in self.docs_dir.glob("*.txt"):
            if txt.stat().st_mtime > index_mtime:
                return False  # có file mới hơn index → build lại
        return True

    def _load_or_build_index(self) -> None:
        """Main init: load cache hoặc build mới."""
        # 1. Thử load từ cache
        if self._load_saved_index():
            return

        # 2. Đọc tài liệu
        self.chunks = self._read_docs()
        texts = [c["text"] for c in self.chunks]
        print(f"[Index] Build mới từ {len(texts)} chunk...")

        # 3. Thử embed bằng Gemini
        vectors = self._embed_batch(texts)
        if vectors is not None:
            try:
                self._faiss_index = self._build_faiss_index(vectors)
                self._save_index(self._faiss_index)
                print("[Index] FAISS index (Gemini Embedding) sẵn sàng.")
                return
            except ImportError:
                print("[Index] faiss-cpu chưa được cài. Dùng TF-IDF fallback.")

        # 4. Fallback: TF-IDF
        self._init_tfidf_fallback(texts)

    def _init_tfidf_fallback(self, texts: list[str]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        print("[Index] Dùng TF-IDF fallback (char n-gram).")
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), norm="l2")
        matrix = vec.fit_transform(texts)
        self._tfidf_fallback = (vec, matrix)

    # ── Search ───────────────────────────────────────────────────────────────
    def search(self, query: str, k: int = TOP_K, min_score: float = MIN_SCORE) -> list[dict]:
        """Trả về tối đa k đoạn liên quan nhất (kèm score và source)."""
        if self._faiss_index is not None:
            return self._search_faiss(query, k, min_score)
        if self._tfidf_fallback:
            return self._search_tfidf(query, k, min_score)
        return []

    def _search_faiss(self, query: str, k: int, min_score: float) -> list[dict]:
        import faiss
        q_vec = self._embed_query(query)
        if q_vec is None:
            if self._tfidf_fallback:
                return self._search_tfidf(query, k, min_score)
            return []

        faiss.normalize_L2(q_vec)
        # Lấy pool ứng viên từ FAISS
        n_candidates = min(max(k * 6, 30), len(self.chunks))
        scores, indices = self._faiss_index.search(q_vec, n_candidates)

        candidates = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            candidates.append({"chunk": self.chunks[idx], "score": float(score), "idx": int(idx)})

        # Source Diversity: giữ tối đa 3 chunk từ mỗi nguồn để tránh 1 nguồn lấn át hoàn toàn,
        # đồng thời không bóp nghẹt các chunk liên quan khác từ cùng nguồn
        candidates = self._ensure_source_diversity(candidates, n_per_source=3)

        # MMR chọn k chunk tốt nhất & đa dạng
        selected = self._mmr(q_vec, candidates, k)
        return [c for c in selected if c["score"] >= min_score]

    def _ensure_source_diversity(self, candidates: list[dict], n_per_source: int = 3) -> list[dict]:
        """Giữ tối đa n_per_source chunk mỗi nguồn ở top, nhưng thêm chunk tốt nhất
        từ những nguồn chưa có vào pool để MMR có thể chọn.
        """
        if not candidates:
            return candidates

        # Nhóm theo source, lấy top-n_per_source mỗi nhóm
        seen: dict[str, int] = {}
        diverse: list[dict] = []
        rest: list[dict] = []
        for c in candidates:  # candidates đã sort theo score giảm dần
            src = c["chunk"]["source"]
            count = seen.get(src, 0)
            if count < n_per_source:
                diverse.append(c)
                seen[src] = count + 1
            else:
                rest.append(c)

        # Thêm best chunk từ các source chưa xuất hiện trong diverse
        seen_in_diverse = set(seen.keys())
        for c in rest:
            src = c["chunk"]["source"]
            if src not in seen_in_diverse:
                diverse.append(c)
                seen_in_diverse.add(src)

        return diverse

    def _mmr(self, q_vec: np.ndarray, candidates: list[dict], k: int, lambda_: float = 0.85) -> list[dict]:
        """
        Maximal Marginal Relevance: cân bằng giữa relevance (giống query)
        và diversity (khác nhau với các chunk đã chọn).
        lambda_ = 0.85 ưu tiên độ liên quan cao đến câu hỏi, chỉ phạt nhẹ nếu quá trùng lặp.
        """
        if not candidates:
            return []

        import faiss  # noqa
        # Lấy vector của tất cả candidates từ FAISS index
        candidate_idxs = [c["idx"] for c in candidates]  # noqa: already int

        selected: list[dict] = []          # dict có key "chunk", "score", "idx"
        remaining = candidates[:]

        while remaining and len(selected) < k:
            if not selected:
                best = max(remaining, key=lambda c: c["score"])
            else:
                sel_vecs = np.vstack([
                    np.array(self._faiss_index.reconstruct(int(c["idx"])), dtype="float32").reshape(1, -1)
                    for c in selected
                ])
                best_mmr_score = -1.0
                best = remaining[0]
                for c in remaining:
                    c_vec = np.array(
                        self._faiss_index.reconstruct(int(c["idx"])), dtype="float32"
                    ).reshape(1, -1)
                    sim_to_selected = float((c_vec @ sel_vecs.T).max())
                    mmr = lambda_ * c["score"] - (1 - lambda_) * sim_to_selected
                    if mmr > best_mmr_score:
                        best_mmr_score = mmr
                        best = c

            selected.append(best)   # giữ toàn bộ dict (gồm cả "idx") để reconstruct tiếp
            remaining = [c for c in remaining if c["idx"] != best["idx"]]

        # Chỉ trả về {"text", "source", "score"} cho caller
        return [{**c["chunk"], "score": c["score"]} for c in selected]

    def _search_tfidf(self, query: str, k: int, min_score: float) -> list[dict]:
        vec, matrix = self._tfidf_fallback
        q_mat = vec.transform([query])
        # cosine similarity (đã L2-norm từ TfidfVectorizer norm="l2")
        scores = (q_mat @ matrix.T).toarray()[0]
        best = scores.argsort()[::-1][:k]
        return [
            {**self.chunks[i], "score": float(scores[i])}
            for i in best
            if scores[i] >= min_score
        ]

    # ── Tiện ích debug ────────────────────────────────────────────────────────
    def rebuild(self) -> None:
        """Xóa cache và build lại index (gọi khi thêm/sửa tài liệu)."""
        if INDEX_FILE.exists():
            INDEX_FILE.unlink()
        if META_FILE.exists():
            META_FILE.unlink()
        self._faiss_index = None
        self._tfidf_fallback = None
        self.chunks = []
        self._load_or_build_index()


# ──────────────────────────────────────────────
# Chạy thử trực tiếp
# ──────────────────────────────────────────────
if __name__ == "__main__":
    r = Retriever()
    queries = [
        "khám bảo hiểm y tế cần giấy tờ gì",
        "giờ làm việc khoa xét nghiệm",
        "tạm ứng viện phí bao nhiêu tiền",
        "chụp MRI mất bao lâu có kết quả",
        "trẻ em dưới 6 tuổi có cần giấy chuyển viện không",
        "khám sản phụ khoa ở đâu",
        "phí khám mắt bao nhiêu",
        "wifi bệnh viện mật khẩu là gì",
    ]
    for q in queries:
        print(f"\n{'='*60}")
        print(f"Câu hỏi: {q}")
        for chunk in r.search(q):
            print(f"  [{chunk['score']:.3f}] {chunk['source']}: {chunk['text'][:120]}...")
