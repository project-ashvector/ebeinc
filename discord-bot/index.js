import {Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder, EmbedBuilder, PermissionFlagsBits} from 'discord.js';

const token = process.env.DISCORD_TOKEN;
const clientId = process.env.DISCORD_CLIENT_ID || '1535406345090502737';
const invite = process.env.DISCORD_INVITE || 'https://discord.gg/3vVzvuXP';
const radioUrl = process.env.RADIO_URL || 'https://allthings140radio.online/';
const statusUrl = 'https://status.ebeinc.online/api/public/status';
if (!token) throw new Error('DISCORD_TOKEN is required. Copy .env.example to .env and set it privately.');

const commands = [
  new SlashCommandBuilder().setName('radio').setDescription('Open the AllThings140 Radio station.'),
  new SlashCommandBuilder().setName('invite').setDescription('Get the permanent community invite.'),
  new SlashCommandBuilder().setName('nowplaying').setDescription('Show the track currently transmitting.'),
  new SlashCommandBuilder().setName('announce').setDescription('Post a station announcement.').addStringOption(o => o.setName('message').setDescription('Announcement text').setRequired(true)).setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
  new SlashCommandBuilder().setName('clear').setDescription('Delete recent messages.').addIntegerOption(o => o.setName('amount').setDescription('1–100 messages').setMinValue(1).setMaxValue(100).setRequired(true)).setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
].map(command => command.toJSON());

const client = new Client({intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMembers]});
const rest = new REST({version: '10'}).setToken(token);

client.once('ready', async ready => {
  await rest.put(Routes.applicationCommands(clientId), {body: commands});
  console.log(`AllThings140 bot online as ${ready.user.tag}`);
});

client.on('guildMemberAdd', async member => {
  const channel = process.env.WELCOME_CHANNEL_ID ? member.guild.channels.cache.get(process.env.WELCOME_CHANNEL_ID) : member.guild.systemChannel;
  if (!channel?.isTextBased()) return;
  await channel.send(`Welcome <@${member.id}> to **AllThings140 Radio**. Tune in at ${radioUrl} and keep the transmission moving. Read the rules, introduce yourself, and enjoy the bass.`).catch(() => {});
});

client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;
  if (interaction.commandName === 'radio') return interaction.reply({content: `Listen live: ${radioUrl}`, ephemeral: true});
  if (interaction.commandName === 'invite') return interaction.reply({content: `Join the community: ${invite}`, ephemeral: true});
  if (interaction.commandName === 'nowplaying') {
    await interaction.deferReply();
    try {
      const response = await fetch(statusUrl, {signal: AbortSignal.timeout(5000)});
      const data = await response.json();
      const isLive = data.mode === 'live' || data.live === true;
      const takeoverArtist = data.active_takeover?.artist || data.live_host;
      const title = data.current_title || data.track?.title || data.title || 'Station rotation';
      const artist = isLive ? (takeoverArtist || 'Guest DJ') : (data.current_artist || data.track?.artist || data.artist || 'AllThings140 Radio');
      const header = isLive ? '🔴 **LIVE TAKEOVER TRANSMITTING**' : '▶ **NOW TRANSMITTING**';
      return interaction.editReply(`${header}\n**${title}** — *${artist}*\n${radioUrl}`);
    } catch { return interaction.editReply(`The station status uplink is unavailable. Listen here: ${radioUrl}`); }
  }
  if (interaction.commandName === 'announce') {
    const message = interaction.options.getString('message', true);
    const embed = new EmbedBuilder().setColor(0xa534e7).setTitle('ALLTHINGS140 RADIO // ANNOUNCEMENT').setDescription(message).setURL(radioUrl).setFooter({text: 'AllThings140 Radio'}).setTimestamp();
    return interaction.reply({embeds: [embed]});
  }
  if (interaction.commandName === 'clear') {
    const amount = interaction.options.getInteger('amount', true);
    if (!interaction.channel?.isTextBased() || !interaction.channel.bulkDelete) return interaction.reply({content: 'This command only works in a text channel.', ephemeral: true});
    const deleted = await interaction.channel.bulkDelete(amount, true);
    return interaction.reply({content: `Deleted ${deleted.size} message${deleted.size === 1 ? '' : 's'}.`, ephemeral: true});
  }
});

client.login(token);
