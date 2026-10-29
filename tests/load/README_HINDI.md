# School Saathi Load Testing — हिन्दी

## यह test क्या करता है?

locustfile.py तीन read-only public endpoints पर synthetic traffic भेजता है: health check, login page और service worker. यह सुरक्षित शुरुआती smoke/load scenario है। यह login के बाद dashboard, fees, attendance, feed या database write paths का performance प्रमाणित **नहीं** करता।

## Staging पर चलाएँ

1. Render या दूसरे provider पर अलग staging service बनाएँ। Production database और real student data का उपयोग न करें।
2. Staging में synthetic school/users बनाएँ और secrets को environment variables में रखें।
3. Python 3.12 virtual environment activate करें।
4. python -m pip install -r requirements.txt और python -m pip install locust चलाएँ।
5. locust -f tests/load/locustfile.py --host https://YOUR-STAGING-HOST चलाएँ।
6. Browser में Locust UI खोलें (आमतौर पर http://localhost:8089)।
7. पहले 10 users और low spawn rate से शुरू करें। Latency, failure rate, web CPU/RAM, PostgreSQL connections और slow queries देखें।
8. Errors बढ़ें या latency target पार हो तो load रोकें; bottleneck ठीक किए बिना users न बढ़ाएँ।

## सावधानियाँ

- Production site पर load test न चलाएँ।
- 5,000 registered customers, 5,000 daily users और 5,000 concurrent users एक जैसे नहीं हैं।
- कोई test “crash कभी नहीं होगा” की guarantee नहीं देता।
- Public endpoint test पास होने का मतलब tenant isolation या private data security सही होना नहीं है।
- Full-scale test से पहले provider की acceptable-use limits और test window की पुष्टि करें।
