/**
 * PM2: `pm2 start ecosystem.config.cjs`
 */
module.exports = {
  apps: [
    {
      name: "crime-research-api",
      cwd: __dirname,
      script: "python",
      args: "-m uvicorn api:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
      instances: 1,
      autorestart: true,
    },
  ],
};
