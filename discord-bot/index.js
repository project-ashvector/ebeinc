import { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder, PermissionFlagsBits, ActivityType, ChannelType } from 'discord.js';
import { AudioPlayerStatus, NoSubscriberBehavior, StreamType, VoiceConnectionStatus, createAudioPlayer, createAudioResource, entersState, joinVoiceChannel } from '@discordjs/voice';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';

const required = (name) => { const value = process.env[name]?.trim(); if (!value) throw new Error(`${name} is required`); return value; };
const token = required('DISCORD_TOKEN');
const clientId = required('DISCORD_CLIENT_ID');
const guildId = required('DISCORD_GUILD_ID');
const voiceChannelId = required('DISCORD_VOICE_CHANNEL_ID');
const radioUrl = process.env.RADIO_URL || 'https://stream.ebeinc.online/live.mp3';
const statusUrl = process.env.STATUS_URL || 'https://status.ebeinc.online/api/public/status';
const healthPort = Number(process.env.HEALTH_PORT || 18401);
const ownerId = process.env.DISCORD_OWNER_ID?.trim();
const ffmpegPath = process.env.FFMPEG_PATH || 'ffmpeg';

const state = { startedAt: Date.now(), reconnects: 0, lastError: '', lastAudioAt: 0, lastStreamAt: 0, ffmpegPid: null, ffmpegStarts: 0, deliberateStop: false };
const commands = [
  new SlashCommandBuilder().setName('radio-status').setDescription('Show ALLTHINGS140 Radio bot health.'),
  new SlashCommandBuilder().setName('nowplaying').setDescription('Show the current ALLTHINGS140 track.'),
  new SlashCommandBuilder().setName('radio-reconnect').setDescription('Reconnect the station voice feed.').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
].map((command) => command.toJSON());

const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
const rest = new REST({ version: '10' }).setToken(token);
const player = createAudioPlayer({ behaviors: { noSubscriber: NoSubscriberBehavior.Play } });
let connection = null;
let ffmpeg = null;
let retryTimer = null;
let healthTimer = null;
let connectAttempt = 0;

function log(message, details = '') { console.log(`[${new Date().toISOString()}] ${message}${details ? ` ${details}` : ''}`); }
function setError(error) { state.lastError = error instanceof Error ? error.message : String(error); log('error', state.lastError); }
function setPresence() { if (client.user) client.user.setPresence({ activities: [{ name: 'ALLTHINGS140 Radio • LIVE', type: ActivityType.Listening }], status: 'online' }); }

async function nowPlaying() {
  try {
    const response = await fetch(statusUrl, { signal: AbortSignal.timeout(5_000) });
    if (!response.ok) throw new Error(`status HTTP ${response.status}`);
    const data = await response.json();
    return { title: data.current_title || data.track?.title || 'Station rotation', artist: data.current_artist || data.track?.artist || 'AllThings140 Radio', online: data.online !== false };
  } catch (error) { setError(`metadata: ${error.message}`); return { title: 'ALLTHINGS140 Radio', artist: 'LIVE', online: false }; }
}

function stopFfmpeg() {
  if (!ffmpeg) return;
  const child = ffmpeg; ffmpeg = null; state.ffmpegPid = null;
  child.stdout?.removeAllListeners(); child.stderr?.removeAllListeners();
  if (!child.killed) child.kill('SIGTERM');
  setTimeout(() => { if (!child.killed) child.kill('SIGKILL'); }, 3_000).unref();
}

function startFfmpeg() {
  stopFfmpeg(); state.ffmpegStarts += 1; log('starting ffmpeg', `attempt=${state.ffmpegStarts}`);
  const child = spawn(ffmpegPath, ['-hide_banner', '-loglevel', 'warning', '-nostdin', '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_at_eof', '1', '-reconnect_delay_max', '10', '-i', radioUrl, '-vn', '-sn', '-dn', '-f', 's16le', '-ar', '48000', '-ac', '2', 'pipe:1'], { stdio: ['ignore', 'pipe', 'pipe'] });
  ffmpeg = child; state.ffmpegPid = child.pid; let bytes = 0;
  child.stdout.on('data', (chunk) => { bytes += chunk.length; state.lastAudioAt = Date.now(); state.lastStreamAt = Date.now(); });
  child.stderr.on('data', (chunk) => { const line = chunk.toString().trim(); if (line) log('ffmpeg', line.slice(0, 300)); });
  child.on('error', (error) => setError(`ffmpeg: ${error.message}`));
  child.on('close', (code, signal) => { if (ffmpeg === child) { ffmpeg = null; state.ffmpegPid = null; log('ffmpeg exited', `code=${code ?? 'null'} signal=${signal ?? 'none'} bytes=${bytes}`); scheduleReconnect('ffmpeg-exit'); } });
  if (connection) player.play(createAudioResource(child.stdout, { inputType: StreamType.Raw }));
}

function scheduleReconnect(reason) {
  if (state.deliberateStop || retryTimer) return;
  connectAttempt += 1; const delay = Math.min(1_000 * 2 ** Math.min(connectAttempt - 1, 6), 60_000); state.reconnects += 1;
  log('reconnect scheduled', `reason=${reason} delay_ms=${delay}`);
  retryTimer = setTimeout(() => { retryTimer = null; connectVoice().catch(setError); }, delay);
}

async function connectVoice() {
  if (state.deliberateStop) return;
  const guild = await client.guilds.fetch(guildId); const channel = await guild.channels.fetch(voiceChannelId);
  if (!channel || channel.type !== ChannelType.GuildVoice) throw new Error('Configured voice channel is not a voice channel');
  if (connection) connection.destroy();
  connection = joinVoiceChannel({ channelId: channel.id, guildId: guild.id, adapterCreator: guild.voiceAdapterCreator, selfDeaf: true, selfMute: true });
  connection.subscribe(player);
  connection.on('stateChange', (oldState, newState) => log('voice state', `${oldState.status} -> ${newState.status}`));
  connection.on('error', (error) => { setError(`voice: ${error.message}`); scheduleReconnect('voice-error'); });
  try { await entersState(connection, VoiceConnectionStatus.Ready, 30_000); connectAttempt = 0; log('voice connected', `channel=${channel.name}`); startFfmpeg(); }
  catch (error) { connection.destroy(); connection = null; throw error; }
}

player.on('stateChange', (oldState, newState) => log('audio player', `${oldState.status} -> ${newState.status}`));
player.on('error', (error) => { setError(`audio player: ${error.message}`); scheduleReconnect('audio-player'); });

async function recoverIfNeeded() {
  if (state.deliberateStop) return;
  if (!connection || connection.state.status === VoiceConnectionStatus.Destroyed || connection.state.status === VoiceConnectionStatus.Disconnected) { scheduleReconnect('voice-unavailable'); return; }
  if (ffmpeg && state.lastAudioAt && Date.now() - state.lastAudioAt > 45_000) { log('audio watchdog restarting stalled ffmpeg'); stopFfmpeg(); scheduleReconnect('audio-stalled'); }
}

function statusSnapshot() { return { ok: Boolean(client.isReady() && connection && connection.state.status === VoiceConnectionStatus.Ready && ffmpeg), discord: client.isReady() ? 'ready' : 'offline', voice: connection?.state.status || 'offline', audio: player.state.status, stream: ffmpeg ? 'connected' : 'offline', ffmpegPid: state.ffmpegPid, lastAudioAt: state.lastAudioAt ? new Date(state.lastAudioAt).toISOString() : null, reconnects: state.reconnects, uptimeSeconds: Math.floor((Date.now() - state.startedAt) / 1000), lastError: state.lastError || null }; }

createServer((request, response) => { if (request.url !== '/health' && request.url !== '/status') { response.writeHead(404); response.end(); return; } const snapshot = statusSnapshot(); response.writeHead(snapshot.ok ? 200 : 503, { 'content-type': 'application/json', 'cache-control': 'no-store' }); response.end(JSON.stringify(snapshot)); }).listen(healthPort, '127.0.0.1', () => log('health endpoint listening', `127.0.0.1:${healthPort}`));

client.once('ready', async () => { log('Discord login complete', `guilds=${client.guilds.cache.size}`); setPresence(); await rest.put(Routes.applicationGuildCommands(clientId, guildId), { body: commands }); log('slash commands registered', `guild=${guildId}`); await connectVoice(); healthTimer = setInterval(recoverIfNeeded, 10_000); healthTimer.unref(); });
client.on('voiceStateUpdate', (oldState, newState) => { if (newState.id === client.user?.id && newState.channelId !== voiceChannelId && !state.deliberateStop) { log('bot moved from configured channel', `channel=${newState.channelId || 'none'}`); scheduleReconnect('voice-state'); } });
client.on('interactionCreate', async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  if (interaction.commandName === 'nowplaying') { const track = await nowPlaying(); return interaction.reply(`🎵 **${track.title}** — *${track.artist}*\n${track.online ? 'LIVE' : 'metadata unavailable'}`); }
  if (interaction.commandName === 'radio-status') return interaction.reply({ content: `\`\`\`json\n${JSON.stringify(statusSnapshot(), null, 2)}\n\`\`\``, ephemeral: true });
  if (interaction.commandName === 'radio-reconnect') { if (ownerId && interaction.user.id !== ownerId && !interaction.memberPermissions?.has(PermissionFlagsBits.ManageGuild)) return interaction.reply({ content: 'Manage Server permission required.', ephemeral: true }); scheduleReconnect('manual'); return interaction.reply({ content: 'Radio voice recovery scheduled.', ephemeral: true }); }
});

async function shutdown(signal) { if (state.deliberateStop) return; state.deliberateStop = true; log('clean shutdown', signal); if (healthTimer) clearInterval(healthTimer); if (retryTimer) clearTimeout(retryTimer); stopFfmpeg(); player.stop(true); connection?.destroy(); client.destroy(); process.exit(0); }
process.on('SIGINT', () => shutdown('SIGINT')); process.on('SIGTERM', () => shutdown('SIGTERM'));
client.login(token).catch((error) => { setError(`Discord login: ${error.message}`); process.exit(1); });
