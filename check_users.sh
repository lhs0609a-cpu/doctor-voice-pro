#!/bin/bash
sqlite3 /data/doctorvoice.db "SELECT email, is_admin FROM users;"
