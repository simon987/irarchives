

# alter table images add hash2 bytea;

from DB import DB
from common import DBFILE


db = DB(DBFILE)
with db.get_conn() as conn:
    update_map = list()
    for row in conn.query("SELECT id, hash FROM videoframes"):
        update_map.append((row[0], bytes(row[1])))


print("Updating %s images" % len(update_map))
input("Continue?")
cnt = len(update_map)

with db.get_conn() as conn:
    for i, update in enumerate(update_map):
        conn.exec("UPDATE videoframes SET hash = %s WHERE id=%s", (update[1], update[0]))
        print("%08d/%08d" % (i, cnt))
