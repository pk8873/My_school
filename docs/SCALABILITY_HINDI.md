# School Saathi — Scale, Security और Production Plan (Hindi)

## उद्देश्य और सीमाएँ

यह दस्तावेज़ 5,000 स्कूलों/ग्राहक खातों या बड़े user base के लिए तैयारी की योजना है। **5,000 customers का अर्थ 5,000 concurrent users नहीं है**। 5,000 registered schools, 5,000 daily active users और 5,000 simultaneous requests तीन अलग workload हैं। कोई भी दस्तावेज़, test या hosting plan crash-free operation की guarantee नहीं देता। वास्तविक क्षमता production-जैसे staging environment में load test, monitoring और capacity tuning के बाद ही पता चलेगी।

इस repository में मौजूद Django/PostgreSQL design को छोटे, backward-compatible बदलावों से आगे बढ़ाएँ। Production database पर सीधे experiments न करें।

## Release gates — वास्तविक school data से पहले

- [ ] DJANGO_DEBUG=False, strong generated DJANGO_SECRET_KEY, correct DJANGO_ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, PostgreSQL DATABASE_URL और HTTPS verified हों।
- [ ] Production secrets GitHub, source code, screenshots या logs में न हों; exposed secrets rotate करें।
- [ ] Backup schedule configured हो और अलग environment में restore drill सफल हो।
- [ ] School/tenant isolation tests list, detail, create, update, delete, PDF, CSV, admin, search, notifications और background jobs cover करें।
- [ ] Parent-to-child and teacher-to-assigned-class authorization tests cover हों।
- [ ] Payment status केवल verified provider webhook / reconciled records से बदले; webhook signature, idempotency और duplicate-event tests हों।
- [ ] Email delivery, password reset, account deactivation, incident contact और data export/deletion process test हों।
- [ ] File uploads private-by-default, size/type validated और backed-up हों।
- [ ] Error monitoring, uptime alerting, database storage/connection monitoring और an on-call owner तय हो।
- [ ] Load tests केवल staging पर synthetic data और test credentials के साथ चलें।

## Scale architecture — incremental path

### Phase 1: Safe single application

1. Managed PostgreSQL रखें; production SQLite या ephemeral local filesystem पर निर्भर न हों।
2. Gunicorn workers/threads को memory, CPU और database connection budget के अनुसार tune करें। Workers को बिना load measurement के बढ़ाना connections और RAM exhaustion कर सकता है।
3. Static files CDN/WhiteNoise के माध्यम से दें। Student documents और private uploads को public static storage में न रखें।
4. प्रत्येक school-scoped query पर tenant filter और server-side permission checks रखें।
5. Query counts और slow query logs staging में देखें; N+1 queries के लिए select_related / prefetch_related और suitable indexes उपयोग करें।
6. Pagination अनिवार्य करें; बड़े student registers/feed को एक response में पूरा न लौटाएँ।
7. CSV/PDF exports के लिए record limits रखें; बड़े exports को बाद में background jobs में ले जाएँ।
8. Database connection pooling का उपयोग केवल provider/driver compatibility जाँचकर करें। Connection pool size × application workers को PostgreSQL connection limit से नीचे रखें।

### Phase 2: Feed और media

- Feed pagination cursor-based या stable date/id pagination से करें; unbounded query न रखें।
- Feed में केवल authorized audience के posts query करें। Visibility को केवल frontend filtering पर निर्भर न रखें।
- Images को resize/compress करें और object storage/CDN में रखें; database में binary media न रखें।
- School-scoped post, notification, membership और feed query paths पर indexes EXPLAIN/realistic data से validate करें।
- Push/email notifications को request के अंदर bulk send न करें; queue/background worker और retry/idempotency policy जोड़ें।
- Cache केवल public/low-risk data का; personalized student/parent data को shared cache में गलती से leak न होने दें।

### Phase 3: Growth और resilience

- पहले metrics collect करें: p50/p95/p99 latency, error rate, requests/sec, CPU/RAM, database connections, slow queries, storage, queue lag और backup age।
- Staging में ramp-up, sustained load और short spike tests करें; हर stage पर errors और latency की stop condition रखें।
- यदि web service saturation दिखे तो app replicas/worker tuning और database capacity को measured bottleneck के आधार पर scale करें।
- भारी exports, bulk imports और notifications को idempotent background jobs में स्थानांतरित करें।
- Restore drills, rollback procedure, migration review और deployment smoke tests हर release में रखें।
- Multi-region या microservices शुरुआत में न जोड़ें; केवल measured need, team capacity और recovery requirements होने पर।

## Load test runbook

Load test को production पर न चलाएँ। Dedicated staging URL और synthetic accounts/data का उपयोग करें। Test credentials को shell environment में रखें, source code में नहीं।

Install:
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m pip install locust

Public endpoint smoke/load test:
    locust -f tests/load/locustfile.py --host https://YOUR-STAGING-HOST

UI में पहले 10 users, फिर 25, 50, 100 की छोटी stages से शुरुआत करें; प्रत्येक stage पर latency/error/DB metrics review करें। 5,000 users तक सीधे jump न करें। बड़े tests को hosting provider की limits और authorization के अनुसार अलग planned window में चलाएँ। इस Locust file के public scenario से authenticated school workflows की capacity प्रमाणित नहीं होती; उन workflows के लिए isolated test accounts और tenant-specific scenarios जोड़ें।

## क्या अभी दावा नहीं करना चाहिए

- “5,000 users guaranteed, never crashes”
- “CBSE/UDISE/APAAR officially integrated” जब तक वास्तविक authorization/integration verified न हो
- “Online payment verified” जब केवल manual ledger entry मौजूद हो
- “Production ready” केवल इसलिए कि manage.py check पास हो गया

## Recommended release sequence

1. Code review + existing test suite + migration check.
2. Staging deployment + synthetic tenant data.
3. Tenant isolation and authorization regression tests.
4. Load tests + query/memory/database tuning.
5. Backup restore + incident/rollback rehearsal.
6. Small pilot school; monitor and fix issues.
7. Gradual onboarding with capacity checks between cohorts.
