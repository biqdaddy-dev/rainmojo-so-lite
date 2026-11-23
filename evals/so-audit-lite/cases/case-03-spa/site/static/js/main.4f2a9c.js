// bundled app (abridged for the snapshot)
const routes={'/':{h1:'Invoicing for freelancers, done in 2 minutes',body:'Send invoices, track payments and chase late clients automatically.'},'/pricing/':{h1:'Pricing',body:'Free for 3 clients. Pro is 9 USD a month.'},'/features/':{h1:'Features',body:'Recurring invoices, reminders, Stripe and PayPal.'},'/blog/':{h1:'Blog',body:'Guides on getting paid on time.'}};
const r=routes[location.pathname]||routes['/'];
document.getElementById('root').innerHTML='<h1>'+r.h1+'</h1><p>'+r.body+'</p>';
