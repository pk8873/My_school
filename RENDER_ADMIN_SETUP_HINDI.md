# Render पर पहला School Admin बनाना (Shell के बिना)

यदि Render Dashboard में Shell उपलब्ध नहीं है, तो इस repository में मौजूद `bootstrap_school_admin` command startup पर school-admin account बना सकती है। यह तभी काम करेगी जब आप नीचे दिए environment variables Render Web Service में manually set करेंगे। कोई password GitHub में न रखें।

## Steps

1. Render Dashboard में `school-saathi` Web Service खोलें और नवीनतम deployment पूरा होने दें।
2. Web Service के **Environment** section में ये पाँच variables जोड़ें:
   - `SCHOOL_BOOTSTRAP_ADMIN_USERNAME` — नया, unique username
   - `SCHOOL_BOOTSTRAP_ADMIN_EMAIL` — admin email
   - `SCHOOL_BOOTSTRAP_ADMIN_PASSWORD` — unique password, कम से कम 12 characters
   - `SCHOOL_BOOTSTRAP_SCHOOL_NAME` — school का नाम
   - `SCHOOL_BOOTSTRAP_SCHOOL_SLUG` — unique lowercase slug, जैसे `my-school-indore`
3. Save changes करें। Render restart/redeploy करेगा। Logs में `Created school admin` की पुष्टि करें।
4. अपनी वेबसाइट के `/accounts/login/` पेज पर नए username/password से login करें।
5. Login सफल होते ही Render Environment में जाकर सभी पाँच `SCHOOL_BOOTSTRAP_...` variables delete करें और changes save करें। उसके बाद command future restarts पर कुछ नहीं करेगी।
6. यदि deployment fail हो, logs से password, email, database URL और secret values हटाकर error साझा करें।

## सुरक्षा और सीमाएँ

- यह command superuser नहीं बनाती; यह school और उससे जुड़ा School Admin membership बनाती है।
- Existing username का password reset नहीं करती। यदि username मौजूद है लेकिन उसी school का active School Admin नहीं है, तो command safety के लिए error देती है।
- Slug पहले से किसी अलग school के लिए इस्तेमाल हो रहा हो तो पहले records review करें।
- वास्तविक विद्यार्थियों का data डालने से पहले security, privacy और backup review करें।