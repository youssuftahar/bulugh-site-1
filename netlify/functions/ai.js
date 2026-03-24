const GROQ_KEY = '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';
const OR_KEY = '';

exports.handler = async (event) => {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json'
  };

  if (event.httpMethod === 'OPTIONS') return { statusCode: 200, headers, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: JSON.stringify({ error: 'Method not allowed' }) };

  try {
    const { prompt, system } = JSON.parse(event.body);
    if (!prompt) return { statusCode: 400, headers, body: JSON.stringify({ error: 'No prompt' }) };

    const models = ['llama-3.1-8b-instant', 'llama3-8b-8192', 'gemma2-9b-it'];
    for (const model of models) {
      try {
        const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + GROQ_KEY },
          body: JSON.stringify({
            model,
            messages: [{ role: 'system', content: system || 'أنت مساعد تعليمي مفيد.' }, { role: 'user', content: prompt }],
            max_tokens: 250
          })
        });
        const data = await res.json();
        if (data.error) continue;
        const text = data.choices?.[0]?.message?.content;
        if (text && text.trim().length > 2) return { statusCode: 200, headers, body: JSON.stringify({ text: text.trim(), source: 'groq' }) };
      } catch (e) { continue; }
    }

    try {
      const res = await fetch('https://text.pollinations.ai/openai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'system', content: system || 'أنت مساعد تعليمي.' }, { role: 'user', content: prompt }],
          model: 'openai', seed: 42, private: true
        })
      });
      const data = await res.json();
      const text = data.choices?.[0]?.message?.content;
      if (text && text.trim().length > 2) return { statusCode: 200, headers, body: JSON.stringify({ text: text.trim(), source: 'pollinations' }) };
    } catch (e) {}

    return { statusCode: 503, headers, body: JSON.stringify({ error: 'unavailable' }) };
  } catch (e) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: e.message }) };
  }
};
