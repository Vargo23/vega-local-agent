from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DIRS = [
    'scripts',
    'core',
    'rag',
    'ui',
    'data',
    'logs',
    'ollama',
    'docs',
    'docs/releases',
    'scripts/checks',
]

REQUIRED_FILES = [
    'README.md',
    'CHANGELOG.md',
    'RELEASE_NOTES.md',
    'PROJECT_STATE.md',
    'scripts/vega.py',
    'scripts/version.py',
    'ui/startup_screen.py',
    'docs/releases/v1.1.0.md',
]

def main():
    errors = []

    for folder in REQUIRED_DIRS:
        path = ROOT / folder
        if not path.exists() or not path.is_dir():
            errors.append(f'Missing folder: {folder}')

    for file in REQUIRED_FILES:
        path = ROOT / file
        if not path.exists() or not path.is_file():
            errors.append(f'Missing file: {file}')

    if errors:
        print('ERROR: project structure check failed')
        print()
        for error in errors:
            print(f'- {error}')
        raise SystemExit(1)

    print('OK: project structure looks valid')

if __name__ == '__main__':
    main()
