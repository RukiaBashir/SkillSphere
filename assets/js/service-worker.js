const CACHE_NAME = 'ict-ticketing-cache-v1';
const urlsToCache = [
    '/',
    '/static/css/bootstrap.min.css',
    '/static/js/bootstrap.bundle.min.js'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                return cache.addAll(urlsToCache);
            })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                return response || fetch(event.request);
            })
    );
});

self.addEventListener('sync', event => {
    if (event.tag === 'sync-tickets') {
        event.waitUntil(syncTickets());
    }
});

async function syncTickets() {
    const db = await openDB('ict_ticketing', 1);
    const tx = db.transaction('tickets', 'readonly');
    const store = tx.objectStore('tickets');
    const allTickets = await store.getAll();

    for (const ticket of allTickets) {
        await fetch('/api/tickets/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': ticket.csrfToken
            },
            body: JSON.stringify(ticket)
        });
        await store.delete(ticket.id);
    }
}

async function openDB(name, version) {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(name, version);

        request.onupgradeneeded = event => {
            const db = event.target.result;
            db.createObjectStore('tickets', { keyPath: 'id', autoIncrement: true });
        };

        request.onsuccess = event => {
            resolve(event.target.result);
        };

        request.onerror = event => {
            reject(event.target.error);
        };
    });
}