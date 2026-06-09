import os
os.environ.setdefault("GOOGLE_API_KEY","test"); os.environ.setdefault("GOOGLE_CX","test")
import lookup as L
MOCK=[{"title":"0302648340 - CÔNG TY CỔ PHẦN ĐẦU TƯ RÔBỐT - MaSoThue","snippet":"Robot Tower, 308-308C Điện Biên Phủ, Phường 04, Quận 3, TP Hồ Chí Minh","link":"https://masothue.com/0302648340-x"},
{"title":"0313756193 - CÔNG TY TNHH AEON TOPVALU VIỆT NAM - MaSoThue","snippet":"Tầng 10, Robot Tower, 308C Điện Biên Phủ, Phường 04, Quận 3","link":"https://masothue.com/0313756193-x"}]
L.google_search=lambda q,k,c,num=10: MOCK
from app import app
app.run(port=5055)
