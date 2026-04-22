from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .answer import WebsiteGroundedAssistant
from .config import INDEX_PATH, PAGES_PATH, Settings, ensure_runtime_dirs
from .indexer import SearchIndex
from .storage import load_documents, save_documents


app = typer.Typer(help="Kafkas Üniversitesi İİBF web sitesi tabanlı chatbot.")
console = Console()


@app.command()
def crawl(
    start_url: Optional[str] = typer.Option(None, help="Başlangıç URL'si."),
    max_pages: Optional[int] = typer.Option(None, help="Taranacak en fazla sayfa sayısı."),
) -> None:
    """Siteyi ve aynı alan adındaki bağlantıları tarar."""
    run_crawl(start_url=start_url, max_pages=max_pages)


@app.command(name="index")
def index_command(
    pages_path: Path = typer.Option(PAGES_PATH, help="Crawl çıktısı JSONL dosyası."),
    index_path: Path = typer.Option(INDEX_PATH, help="Oluşturulacak indeks dosyası."),
) -> None:
    """Kaydedilmiş site içeriklerinden arama indeksi üretir."""
    run_index(pages_path=pages_path, index_path=index_path)


@app.command()
def refresh(
    start_url: Optional[str] = typer.Option(None, help="Başlangıç URL'si."),
    max_pages: Optional[int] = typer.Option(None, help="Taranacak en fazla sayfa sayısı."),
) -> None:
    """Siteyi yeniden tarar ve indeksi tazeler."""
    run_crawl(start_url=start_url, max_pages=max_pages)
    run_index()


def run_crawl(start_url: Optional[str] = None, max_pages: Optional[int] = None) -> int:
    from .crawler import WebsiteCrawler

    ensure_runtime_dirs()
    settings = Settings()
    crawler = WebsiteCrawler(settings)
    documents = crawler.crawl(start_url=start_url, max_pages=max_pages)
    count = save_documents(PAGES_PATH, documents)
    console.print(f"[green]{count} belge kaydedildi:[/green] {PAGES_PATH}")
    return count


def run_index(pages_path: Path = PAGES_PATH, index_path: Path = INDEX_PATH) -> int:
    documents = load_documents(pages_path)
    if not documents:
        raise typer.BadParameter(f"Belge bulunamadı: {pages_path}")

    search_index = SearchIndex.build(documents, Settings())
    search_index.save(index_path)
    console.print(
        f"[green]{len(search_index.chunks)} metin parçası indekslendi:[/green] {index_path}"
    )
    return len(search_index.chunks)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Kullanıcı sorusu."),
) -> None:
    """İndekslenmiş site içeriğine dayanarak yanıt verir."""
    if not INDEX_PATH.exists():
        raise typer.BadParameter(
            "Önce `python -m kau_can_bot refresh` komutu ile siteyi indeksleyiniz."
        )

    assistant = WebsiteGroundedAssistant()
    console.print(assistant.answer(question))


if __name__ == "__main__":
    app()
