# from src.parser import parse_all_statements;
# from pathlib import Path;
#
# BASE_DIR = Path(__file__).resolve().parent.parent.parent;
# print(BASE_DIR);
# STATEMENTS_DIR = BASE_DIR / 'data' / 'statements';
# print(STATEMENTS_DIR);
# df = parse_all_statements(STATEMENTS_DIR);
# print(f'✅ Refreshed {len(df)} transactions')
#

from src.build_master import build_master; df = build_master(); print(f'✅ Refreshed {len(df)} transactions')
