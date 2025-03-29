// static/js/app.js
let db;
const request = indexedDB.open('ticketDB', 1);

request.onupgradeneeded = event => {
  db = event.target.result;
  db.createObjectStore('tickets', { keyPath: 'id', autoIncrement: true });
};

request.onsuccess = event => {
  db = event.target.result;
};

function saveTicketOffline(ticket) {
  const transaction = db.transaction(['tickets'], 'readwrite');
  const store = transaction.objectStore('tickets');
  store.add(ticket);
}

function syncTickets() {
  const transaction = db.transaction(['tickets'], 'readonly');
  const store = transaction.objectStore('tickets');
  const request = store.getAll();

  request.onsuccess = async event => {
    const tickets = event.target.result;
    for (const ticket of tickets) {
      // Send to server
      const response = await fetch('/ticket/new/', {
        method: 'POST',
        body: JSON.stringify(ticket),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (response.ok) {
        // Remove from IndexedDB
        const deleteTransaction = db.transaction(['tickets'], 'readwrite');
        const deleteStore = deleteTransaction.objectStore('tickets');
        deleteStore.delete(ticket.id);
      }
    }
  };
}

window.addEventListener('online', syncTickets);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/static/js/service-worker.js').then(function(registration) {
      console.log('ServiceWorker registration successful with scope: ', registration.scope);
    }, function(error) {
      console.log('ServiceWorker registration failed: ', error);
    });
  });
}