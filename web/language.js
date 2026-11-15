// Shared English/Hinglish UI language. Raw model IDs, file paths, and logs stay unchanged.
(() => {
  const translations = {"Model library": "Model library","Dashboard": "Dashboard", "Help & workflow": "Madad aur workflow", "Connecting…": "Connect ho raha hai…", "YOUR LOCAL MODEL ARCHIVE": "AAPKI LOCAL MODEL LIBRARY", "A home for your models.": "Aapke models ka apna ghar.", "Pinned revisions. Verified files. Durable recovery on your external drive.": "Fixed versions, verified files aur external drive par safe download recovery.", "PINNED QUEUE": "FIXED DOWNLOAD QUEUE", "TOTAL SIZE": "TOTAL SIZE", "FILES PRESENT": "DISK PAR FILES", "DRIVE FREE": "DRIVE PAR KHALI JAGAH", "Explore your queue": "Apni queue explore karo", "Click any count to filter the queue. Combine different segments to drill down. Counts describe the full pinned queue.": "Kisi count par click karke queue filter karo. Alag segments combine karke aur detail dekho. Counts poori pinned queue ke hain.", "Clear filters": "Filters hatao", "All models": "Saare models", "All segments": "Saare segments", "Abliterated = refusal-reduced modification · Uncensored = fine-tune labeled for fewer restrictions · General = broad-purpose. Labels come from your catalog; they are not behavior guarantees. Publisher is the Hugging Face repository owner.": "Abliterated = refusal kam karne ke liye modified · Uncensored = fewer restrictions wala fine-tune · General = general tasks. Labels catalog se hain, behavior ki guarantee nahi. Publisher Hugging Face repo ka owner hai.", "Download queue": "Download queue", "Present files are re-hashed by the downloader before reuse. Partial progress below counts only durable checkpoints.": "Existing files reuse se pehle hash-check hoti hain. Partial progress mein sirf safely checkpointed bytes count hote hain.", "I reviewed this pinned queue and its storage requirements.": "Maine poori pinned queue aur uski storage requirement review kar li hai.", "Start / Resume": "Start / Resume", "Verify files": "Files verify karo", "Stop safely": "Safely roko", "Controls apply to the entire pinned queue, including models hidden by filters. Nothing starts automatically. Stop retains partial files and checkpoints. Existing CLI and login workers share the same exclusive lock.": "Controls poori pinned queue par lagte hain, filters se hidden models par bhi. Kuch automatically start nahi hota. Stop par partial files aur checkpoints rehte hain. CLI aur login workers bhi same lock use karte hain.", "Worker activity": "Worker ki activity", "Idle": "Idle", "No dashboard worker has run.": "Abhi tak koi dashboard worker nahi chala.", "Catalog changes and fresh planning use the existing CLI. Your current pinned queue stays unchanged.": "Catalog changes aur naya plan banane ke liye CLI use karo. Current pinned queue apne aap nahi badalti.", "LOCAL ONLY · 20 GiB default reserve · SHA-256 / Git blob verification · fsync checkpoints": "SIRF LOCAL · 20 GiB default reserve · SHA-256 / Git blob verification · fsync checkpoints", "By category / behavior": "Category / behavior ke hisaab se", "By publisher": "Publisher ke hisaab se", "By download status": "Download status ke hisaab se", "By format": "Format ke hisaab se", "By license": "License ke hisaab se", "Unknown": "Unknown", "Needs attention": "Dhyan chahiye", "Queued": "Queue mein", "Partial": "Adhoora", "Downloaded": "Downloaded", "View files, pinned revision & license": "Files, fixed version aur license dekho", "See model card": "Model card dekho", "No models match. Clear filters to see the full queue.": "Koi model match nahi hua. Poori queue dekhne ke liye filters hatao.", "No downloaded files yet — verification becomes available after files are downloaded.": "Abhi koi downloaded file nahi hai — files aane ke baad verification available hoga.", "Verification checks the full queue and reports missing or corrupt files.": "Verification poori queue check karta hai aur missing/corrupt files batata hai.", "No downloaded files to verify": "Verify karne ke liye downloaded files nahi hain", "Verify downloaded files; report missing files": "Downloaded files verify karo; missing files report karo", "Status unavailable": "Status available nahi hai", "● Drive connected": "● Drive connected hai", "○ Needs attention": "○ Dhyan chahiye", "Drive unavailable. Showing the last saved queue from SQLite; download controls are disabled. ": "Drive available nahi hai. SQLite se last saved queue dikh rahi hai; download controls disabled hain. ", "Queue ready for review. Downloads start only when you choose Start / Resume.": "Queue review ke liye ready hai. Download sirf Start / Resume choose karne par shuru hoga.", "No drive configured": "Drive configure nahi hai", "Disconnected": "Connection toot gaya", "Filter models or categories": "Models ya categories filter karo", "Filter queue": "Queue filter karo", "Language": "Language / Bhasha", "A SMALL GUIDE TO YOUR ARCHIVE": "AAPKI LIBRARY KI CHHOTI GUIDE", "Help & workflow · Model Vault": "Madad aur workflow · Model Vault", "models": "models", "files": "files", "durable": "safely saved", "enabled": "enabled", "disabled": "disabled", "Revision": "Version", "License": "License", "Running: ": "Chal raha hai: ", "Exited: ": "Exit hua: ", "Catalog ·": "Catalog ·", "available models": "available models", "Showing {shown} of {total} models": "{total} mein se {shown} models dikh rahe hain", "{count} models": "{count} models", "{count} files": "{count} files", "{count} GiB reserved": "{count} GiB reserve hai", "Filter by {tag}": "{tag} se filter karo"};
  let language = 'en';
  try { if (localStorage.getItem('model-vault-language') === 'hi') language = 'hi'; } catch (_) {}
  const originalText = new WeakMap();
  function t(text, params = {}) {
    let value = language === 'hi' ? (translations[text] || text) : text;
    for (const [key, replacement] of Object.entries(params)) value = value.replaceAll('{' + key + '}', replacement);
    return value;
  }
  function apply() {
    document.documentElement.lang = language === 'hi' ? 'hi-Latn' : 'en';
    document.querySelectorAll('[data-language]').forEach(e => { e.hidden = e.dataset.language !== language; });
    document.querySelectorAll('[data-translate]').forEach(e => {
      // Help article bodies are independently authored in both languages.
      if (e.dataset.translate === 'text') {
        if (!originalText.has(e)) originalText.set(e, e.textContent);
        e.textContent = t(originalText.get(e));
      }
    });
    document.querySelectorAll('[data-en-placeholder]').forEach(e => { e.placeholder = t(e.dataset.enPlaceholder); });
    document.querySelectorAll('[data-en-label]').forEach(e => { e.setAttribute('aria-label', t(e.dataset.enLabel)); });
    document.querySelectorAll('[data-language-button]').forEach(e => e.setAttribute('aria-pressed', String(e.dataset.languageButton === language)));
    document.title = t(document.body.dataset.englishTitle || document.title);
  }
  window.MVLanguage = {t, get: () => language};
  const picker = document.createElement('div'); picker.className = 'language-switch'; picker.setAttribute('role', 'group'); picker.setAttribute('aria-label', 'Language / Bhasha');
  for (const [value, label] of [['en', 'English'], ['hi', 'Hinglish']]) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = label; button.dataset.languageButton = value;
    button.addEventListener('click', () => {
      language = value;
      try { localStorage.setItem('model-vault-language', language); } catch (_) {}
      apply(); window.dispatchEvent(new Event('languagechange'));
    }); picker.append(button);
  }
  document.querySelector('header nav').append(picker);
  apply();
})();
