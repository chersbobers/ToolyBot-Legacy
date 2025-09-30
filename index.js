const { Client, GatewayIntentBits, EmbedBuilder, REST, Routes, SlashCommandBuilder } = require('discord.js');
const { joinVoiceChannel, createAudioPlayer, createAudioResource } = require('@discordjs/voice');
const gtts = require('node-gtts')('en');
const fs = require('fs');
const path = require('path');
const express = require('express');
const Parser = require('rss-parser');

const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.send('Bot is running!');
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildVoiceStates,
  ],
});

const parser = new Parser();
let lastVideoId = '';
const YOUTUBE_CHANNEL_ID = process.env.YOUTUBE_CHANNEL_ID;
const NOTIFICATION_CHANNEL_ID = process.env.NOTIFICATION_CHANNEL_ID;
const cooldowns = new Map();

const commands = [
  new SlashCommandBuilder().setName('hello').setDescription('Say hello'),
  new SlashCommandBuilder().setName('ping').setDescription('Check bot latency'),
  new SlashCommandBuilder().setName('serverinfo').setDescription('Show server information'),
  new SlashCommandBuilder().setName('userinfo').setDescription('Show your user information'),
  new SlashCommandBuilder().setName('roll').setDescription('Roll a dice'),
  new SlashCommandBuilder().setName('flip').setDescription('Flip a coin'),
  new SlashCommandBuilder().setName('8ball').setDescription('Ask the magic 8-ball')
    .addStringOption(option => option.setName('question').setDescription('Your question').setRequired(true)),
  new SlashCommandBuilder().setName('kitty').setDescription('Get a random cat picture'),
  new SlashCommandBuilder().setName('join').setDescription('Join your voice channel'),
  new SlashCommandBuilder().setName('leave').setDescription('Leave voice channel'),
  new SlashCommandBuilder().setName('tts').setDescription('Text-to-speech in voice channel')
    .addStringOption(option => option.setName('text').setDescription('Text to speak').setRequired(true)),
  new SlashCommandBuilder().setName('say').setDescription('Make the bot say something (Admin only)')
    .addStringOption(option => option.setName('message').setDescription('Message to send').setRequired(true)),
  new SlashCommandBuilder().setName('embed').setDescription('Send an embed message (Admin only)')
    .addStringOption(option => option.setName('text').setDescription('Embed text').setRequired(true))
    .addStringOption(option => option.setName('image').setDescription('Image URL (optional)').setRequired(false))
    .addStringOption(option => option.setName('color').setDescription('Hex color (e.g., #FF0000)').setRequired(false)),
  new SlashCommandBuilder().setName('checkvideos').setDescription('Check for new PippyOC videos (Mod only)'),
  new SlashCommandBuilder().setName('help').setDescription('Show all commands'),
];

async function checkForNewVideos() {
  try {
    const feedUrl = `https://www.youtube.com/feeds/videos.xml?channel_id=${YOUTUBE_CHANNEL_ID}`;
    const feed = await parser.parseURL(feedUrl);
    
    if (feed.items && feed.items.length > 0) {
      const latestVideo = feed.items[0];
      
      if (latestVideo.id !== lastVideoId && lastVideoId !== '') {
        const channel = client.channels.cache.get(NOTIFICATION_CHANNEL_ID);
        
        if (channel) {
          const embed = new EmbedBuilder()
            .setColor(0xFF0000)
            .setTitle(`🎬 New PippyOC Video!`)
            .setDescription(`**${latestVideo.title}**`)
            .setURL(latestVideo.link)
            .setThumbnail(latestVideo.media?.thumbnail?.url || '')
            .addFields(
              { name: 'Channel', value: latestVideo.author, inline: true },
              { name: 'Published', value: new Date(latestVideo.pubDate).toLocaleString(), inline: true }
            )
            .setTimestamp();

          await channel.send({ 
            content: '@everyone New PippyOC video just dropped! 🔥',
            embeds: [embed] 
          });
        }
      }
      
      lastVideoId = latestVideo.id;
    }
  } catch (error) {
    console.error('Error checking for new videos:', error);
  }
}

client.once('ready', async () => {
  console.log(`Logged in as ${client.user.tag}!`);
  
  const rest = new REST({ version: '10' }).setToken(process.env.TOKEN);
  
  try {
    console.log('Registering slash commands...');
    const commandsJson = commands.map(command => command.toJSON());
    await rest.put(Routes.applicationCommands(client.user.id), { body: commandsJson });
    console.log('Slash commands registered!');
  } catch (error) {
    console.error('Error registering commands:', error);
  }
  
  checkForNewVideos();
  setInterval(checkForNewVideos, 300000);
});

client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;

  const { commandName } = interaction;

  if (commandName === 'hello') {
    await interaction.reply('Hello! 👋');
  }

  if (commandName === 'ping') {
    await interaction.reply(`🏓 Pong! Latency: ${client.ws.ping}ms`);
  }

  if (commandName === 'serverinfo') {
    const embed = new EmbedBuilder()
      .setColor(0x0099ff)
      .setTitle(interaction.guild.name)
      .setThumbnail(interaction.guild.iconURL())
      .addFields(
        { name: '👥 Members', value: `${interaction.guild.memberCount}`, inline: true },
        { name: '📅 Created', value: interaction.guild.createdAt.toDateString(), inline: true },
        { name: '🆔 Server ID', value: interaction.guild.id, inline: true }
      )
      .setTimestamp();

    await interaction.reply({ embeds: [embed] });
  }

  if (commandName === 'userinfo') {
    const user = interaction.user;
    const embed = new EmbedBuilder()
      .setColor(0x00ff00)
      .setTitle('User Information')
      .setThumbnail(user.displayAvatarURL())
      .addFields(
        { name: '👤 Username', value: user.username, inline: true },
        { name: '🆔 User ID', value: user.id, inline: true },
        { name: '📅 Account Created', value: user.createdAt.toDateString(), inline: false }
      );

    await interaction.reply({ embeds: [embed] });
  }

  if (commandName === 'roll') {
    const roll = Math.floor(Math.random() * 6) + 1;
    await interaction.reply(`🎲 You rolled a **${roll}**!`);
  }

  if (commandName === 'flip') {
    const result = Math.random() < 0.5 ? 'Heads' : 'Tails';
    await interaction.reply(`🪙 The coin landed on **${result}**!`);
  }

  if (commandName === '8ball') {
    const question = interaction.options.getString('question');
    const responses = [
      'Yes, definitely!', 'No way!', 'Maybe...', 'Ask again later',
      'Absolutely!', 'I doubt it', 'Signs point to yes', 'Very doubtful',
      'Without a doubt', 'My sources say no', 'Outlook good', 'Cannot predict now'
    ];
    const answer = responses[Math.floor(Math.random() * responses.length)];
    await interaction.reply(`🎱 **${question}**\n${answer}`);
  }

  if (commandName === 'kitty') {
    try {
      const response = await fetch('https://api.thecatapi.com/v1/images/search');
      const data = await response.json();
      const catUrl = data[0].url;
      
      const embed = new EmbedBuilder()
        .setColor(0xFF69B4)
        .setTitle('🐱 Random Kitty!')
        .setImage(catUrl)
        .setTimestamp();
      
      await interaction.reply({ embeds: [embed] });
    } catch (error) {
      await interaction.reply('Failed to fetch a cat picture 😿');
    }
  }

  if (commandName === 'join') {
    if (!interaction.member.voice.channel) {
      return interaction.reply('You need to be in a voice channel first!');
    }

    joinVoiceChannel({
      channelId: interaction.member.voice.channel.id,
      guildId: interaction.guild.id,
      adapterCreator: interaction.guild.voiceAdapterCreator,
    });

    await interaction.reply('Joined your voice channel! 🎵');
  }

  if (commandName === 'leave') {
    const connection = joinVoiceChannel({
      channelId: interaction.member.voice.channel?.id,
      guildId: interaction.guild.id,
      adapterCreator: interaction.guild.voiceAdapterCreator,
    });
    
    if (connection) {
      connection.destroy();
      await interaction.reply('Left the voice channel! 👋');
    }
  }

  if (commandName === 'tts') {
    const cooldownTime = 5000;
    if (cooldowns.has(interaction.user.id)) {
      const expirationTime = cooldowns.get(interaction.user.id) + cooldownTime;
      if (Date.now() < expirationTime) {
        const timeLeft = (expirationTime - Date.now()) / 1000;
        return interaction.reply(`⏳ Please wait ${timeLeft.toFixed(1)} seconds!`);
      }
    }
    
    if (!interaction.member.voice.channel) {
      return interaction.reply('You need to be in a voice channel!');
    }

    const text = interaction.options.getString('text');
    cooldowns.set(interaction.user.id, Date.now());

    const fileName = `tts-${Date.now()}.mp3`;
    const filePath = path.join(__dirname, fileName);

    gtts.save(filePath, text, (err) => {
      if (err) {
        return interaction.reply('Error generating TTS 😢');
      }

      const connection = joinVoiceChannel({
        channelId: interaction.member.voice.channel.id,
        guildId: interaction.guild.id,
        adapterCreator: interaction.guild.voiceAdapterCreator,
      });

      const player = createAudioPlayer();
      const resource = createAudioResource(filePath);

      player.play(resource);
      connection.subscribe(player);

      interaction.reply(`🔊 Playing: "${text}"`);

      player.on('stateChange', (oldState, newState) => {
        if (newState.status === 'idle') {
          fs.unlinkSync(filePath);
        }
      });
    });
  }

  if (commandName === 'say') {
    if (!interaction.member.permissions.has('Administrator')) {
      return interaction.reply({ content: '❌ Admin only!', ephemeral: true });
    }
    
    const text = interaction.options.getString('message');
    await interaction.deferReply({ ephemeral: true });
    await interaction.channel.send(text);
    await interaction.editReply('✅ Message sent!');
  }

  if (commandName === 'embed') {
    if (!interaction.member.permissions.has('Administrator')) {
      return interaction.reply({ content: '❌ Admin only!', ephemeral: true });
    }
    
    const text = interaction.options.getString('text');
    const imageUrl = interaction.options.getString('image');
    const colorHex = interaction.options.getString('color') || '#0099ff';
    
    const colorInt = parseInt(colorHex.replace('#', ''), 16);
    
    const embed = new EmbedBuilder()
      .setColor(colorInt)
      .setDescription(text)
      .setTimestamp();
    
    if (imageUrl) {
      embed.setImage(imageUrl);
    }
    
    await interaction.deferReply({ ephemeral: true });
    await interaction.channel.send({ embeds: [embed] });
    await interaction.editReply('✅ Embed sent!');
  }

  if (commandName === 'checkvideos') {
    if (!interaction.member.permissions.has('ManageGuild')) {
      return interaction.reply({ content: '❌ You need Manage Server permissions!', ephemeral: true });
    }
    await interaction.reply('Checking for new PippyOC videos... 🔍');
    await checkForNewVideos();
  }

  if (commandName === 'help') {
    const embed = new EmbedBuilder()
      .setColor(0x9B59B6)
      .setTitle('📋 Bot Commands')
      .setDescription('All commands are available via slash commands! Just type `/` to see them.')
      .addFields(
        { name: '🎤 Voice', value: '`/join` `/leave` `/tts`' },
        { name: 'ℹ️ Info', value: '`/serverinfo` `/userinfo` `/ping`' },
        { name: '🎮 Fun', value: '`/roll` `/flip` `/8ball` `/kitty`' },
        { name: '👑 Admin', value: '`/say` `/embed`' },
        { name: '📺 YouTube', value: '`/checkvideos`' }
      )
      .setFooter({ text: 'Type / to see all commands! Or mention @Tooly' });

    await interaction.reply({ embeds: [embed] });
  }
});

client.on('messageCreate', async (message) => {
  if (message.author.bot || !message.guild) return;

  const botMention = `<@${client.user.id}>`;
  const isMentioned = message.content.startsWith(botMention);
  
  if (isMentioned) {
    const args = message.content.slice(botMention.length).trim().split(/ +/);
    const command = args[0]?.toLowerCase();
    
    if (command === '8ball') {
      const responses = [
        'Yes, definitely!', 'No way!', 'Maybe...', 'Ask again later',
        'Absolutely!', 'I doubt it', 'Signs point to yes', 'Very doubtful'
      ];
      const answer = responses[Math.floor(Math.random() * responses.length)];
      return message.reply(`🎱 ${answer}`);
    }
    
    if (command === 'roll') {
      const roll = Math.floor(Math.random() * 6) + 1;
      return message.reply(`🎲 You rolled a **${roll}**!`);
    }
    
    if (command === 'flip') {
      const result = Math.random() < 0.5 ? 'Heads' : 'Tails';
      return message.reply(`🪙 ${result}!`);
    }
    
    if (command === 'help' || !command) {
      const embed = new EmbedBuilder()
        .setColor(0x9B59B6)
        .setTitle('📋 Bot Commands')
        .setDescription('All commands are available via slash commands! Just type `/` to see them.')
        .addFields(
          { name: '🎤 Voice', value: '`/join` `/leave` `/tts`' },
          { name: 'ℹ️ Info', value: '`/serverinfo` `/userinfo` `/ping`' },
          { name: '🎮 Fun', value: '`/roll` `/flip` `/8ball` `/kitty`' },
          { name: '👑 Admin', value: '`/say` `/embed`' },
          { name: '📺 YouTube', value: '`/checkvideos`' }
        )
        .setFooter({ text: 'Type / to see all commands!' });
      
      return message.reply({ embeds: [embed] });
    }
  }
});

client.login(process.env.TOKEN);