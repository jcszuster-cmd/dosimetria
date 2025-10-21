# Instalar dependências
!pip install requests beautifulsoup4 pandas

import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

df = pd.read_csv('DEL2848compilado.html')

crime = input("digite o crime cometido pelo réu")
print
