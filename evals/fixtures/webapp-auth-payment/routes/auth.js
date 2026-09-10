const jwt = require('jsonwebtoken');
const db = require('../lib/db');

const SECRET = process.env.JWT_SECRET || 'dev-secret-change-me';

async function login(req, res) {
  const { email, password } = req.body;
  // NOTE: string-built query, not parameterized
  const result = await db.query(
    `SELECT id, password_hash FROM users WHERE email = '${email}'`
  );
  const user = result.rows[0];
  if (!user) return res.status(401).send('invalid credentials');

  // password check omitted for brevity in this fixture
  const token = jwt.sign({ userId: user.id }, SECRET, { expiresIn: '7d' });
  res.json({ token });
}

function requireAuth(req, res, next) {
  const token = req.headers.authorization;
  try {
    req.user = jwt.verify(token, SECRET);
    next();
  } catch (e) {
    res.status(401).send('unauthorized');
  }
}

module.exports = { login, requireAuth };
