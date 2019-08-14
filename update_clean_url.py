

# alter table imageurls add clean_url TEXT;
# drop index imageurls_url_index;
# create index imageurls_clean_url_index on imageurls (clean_url);

from DB import DB
from common import DBFILE
from util import clean_url

db = DB(DBFILE)
with db.get_conn() as conn:
    update_map = list()
    for row in conn.query("SELECT id, url FROM ir.public.imageurls"):
        update_map.append((row[0], clean_url(row[1])))

print("Updating %s imageurls" % len(update_map))
input("Continue?")

with db.get_conn() as conn:
    for i, update in enumerate(update_map):
        conn.exec("UPDATE imageurls SET clean_url = %s WHERE id=%s", (update[1], update[0]))
        print("%08d/%08d" % (i, len(update_map)))

