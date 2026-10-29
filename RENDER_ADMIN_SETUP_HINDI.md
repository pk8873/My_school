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

## Password reset email (नई सुविधा)

अब login page पर **Forgot your password?** link उपलब्ध है। यह केवल उस active account के लिए reset email भेजता है जिसमें email address पहले से दर्ज है। पेज यह खुलासा नहीं करता कि कोई email registered है या नहीं।

### Render में SMTP सेट करना

1. Render Dashboard → अपनी Web Service → **Environment** खोलें।
2. अपने email provider के SMTP विवरण से ये variables जोड़ें: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` और `DEFAULT_FROM_EMAIL`.
3. उदाहरण के लिए, STARTTLS provider आम तौर पर port `587` और `EMAIL_USE_TLS=True` उपयोग करता है; अपने provider की documentation के अनुसार values भरें। असली values provider के अनुसार अलग होंगी।
4. Save changes करके redeploy/restart होने दें। पहले अपने ही test account पर reset email जाँचें; inbox और spam folder दोनों देखें।
5. SMTP password को केवल Render Environment में रखें। उसे GitHub, source code, screenshots या chat में न डालें।

Local development में reset email terminal/console में दिखाई जाती है। Production में SMTP credentials configure किए बिना email delivery काम करने की गारंटी नहीं है।

## सुरक्षा और सीमाएँ

- यह command superuser नहीं बनाती; यह school और उससे जुड़ा School Admin membership बनाती है।
- Existing username का password reset नहीं करती। यदि username मौजूद है लेकिन उसी school का active School Admin नहीं है, तो command safety के लिए error देती है।
- Slug पहले से किसी अलग school के लिए इस्तेमाल हो रहा हो तो पहले records review करें।
- वास्तविक विद्यार्थियों का data डालने से पहले security, privacy और backup review करें।
