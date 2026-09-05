document.addEventListener('DOMContentLoaded', () => {
    const userIdInput = document.getElementById('userIdInput');
    const saveBtn = document.getElementById('saveBtn');
    const saveStatus = document.getElementById('saveStatus');

    // Load existing ID
    chrome.storage.local.get(['userId'], (result) => {
        if (result.userId) {
            userIdInput.value = result.userId;
        }
    });

    // Save ID
    saveBtn.addEventListener('click', () => {
        const userId = userIdInput.value.trim();
        chrome.storage.local.set({ userId: userId }, () => {
            saveStatus.style.display = 'block';
            setTimeout(() => {
                saveStatus.style.display = 'none';
            }, 2000);
        });
    });
});
