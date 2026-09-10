const stripe = require('stripe')(process.env.STRIPE_KEY);
const db = require('../lib/db');

// Stripe webhook handler — no signature verification, no retry/idempotency handling
async function handleWebhook(req, res) {
  const event = req.body; // raw JSON, not verified against Stripe signature

  if (event.type === 'payment_intent.succeeded') {
    const userId = event.data.object.metadata.userId;
    const amount = event.data.object.amount;

    // two separate writes, no transaction wrapping them
    await db.query(`UPDATE users SET balance = balance + ${amount} WHERE id = ${userId}`);
    await db.query(`INSERT INTO payment_log (user_id, amount) VALUES (${userId}, ${amount})`);
  }

  res.sendStatus(200);
}

module.exports = { handleWebhook };
