#!/usr/bin/env python3
import pathlib

def process_file(file_path: pathlib.Path) -> None:
    """
    Öppnar filen, byter ut '![](_page' mot '![](images/_page'
    och skriver tillbaka om ändringar görs.
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Misslyckades läsa {file_path}: {e}")
        return

    # Ersätt alla förekomster av den gamla strängen med den nya
    new_content = content.replace("![](_page", "![](images/_page")

    # Skriv tillbaka filen endast om ändringar skett
    if new_content != content:
        try:
            file_path.write_text(new_content, encoding='utf-8')
            print(f"Uppdaterad: {file_path}")
        except Exception as e:
            print(f"Misslyckades skriva {file_path}: {e}")
    else:
        print(f"Inga ändringar i: {file_path}")

def main() -> None:
    # Basmappen med alla filer
    base_path = pathlib.Path("./integrated_data")
    # Filtyper att processa
    allowed_extensions = {".md", ".json", ".jsonl"}

    if not base_path.exists():
        print(f"Katalogen {base_path} hittades inte.")
        return

    # Gå igenom alla filer i katalogen (rekursivt)
    for file_path in base_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in allowed_extensions:
            process_file(file_path)

if __name__ == "__main__":
    main()
