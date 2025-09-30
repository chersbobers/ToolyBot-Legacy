const { Client, GatewayIntentBits, EmbedBuilder } = require('discord.js');
const { joinVoiceChannel, createAudioPlayer, createAudioResource } = require('@discordjs/voice');
const gtts = require('node-gtts')('en');
const fs = require('fs');
const path = require('path');
const express = require('express');
const Parser = require('rss-parser');

// Create Express app
const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.send('Bot is running!');
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

// Create Discord client
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildVoiceStates,
  ],
});

const parser = new Parser();

// Store last video ID to avoid duplicate notifications
let lastVideoId = '';

// YouTube channel ID for PippyOC - UPDATE THIS WITH THE ACTUAL CHANNEL ID
const YOUTUBE_CHANNEL_ID = 'UCLDKWUO9mwlcvvcm6ezK9AQ';
const NOTIFICATION_CHANNEL_ID = '1374822032579231745'; // Where to post notifications

// Check for new videos every 5 minutes
async function checkForNewVideos() {
  try {
    const feedUrl = `https://www.youtube.com/feeds/videos.xml?channel_id=${YOUTUBE_CHANNEL_ID}`;
    const feed = await parser.parseURL(feedUrl);
    
    if (feed.items && feed.items.length > 0) {
      const latestVideo = feed.items[0];
      
      // If this is a new video (different from last check)
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

// When bot is ready
client.once('ready', () => {
  console.log(`Logged in as ${client.user.tag}!`);
  
  // Initialize lastVideoId on startup
  checkForNewVideos();
  
  // Check for new videos every 5 minutes (300000 ms)
  setInterval(checkForNewVideos, 300000);
});

// Message commands
client.on('messageCreate', async (message) => {
  if (message.author.bot) return;

  // ===== BASIC COMMANDS =====
  if (message.content === '!hello') {
    message.reply('Hello! 👋');
  }

  if (message.content === '!ping') {
    const sent = await message.reply('Pinging...');
    const ping = sent.createdTimestamp - message.createdTimestamp;
    sent.edit(`🏓 Pong! Latency: ${ping}ms`);
  }

  // ===== VOICE COMMANDS =====
  if (message.content === '!join') {
    if (!message.member.voice.channel) {
      return message.reply('You need to be in a voice channel first!');
    }

    joinVoiceChannel({
      channelId: message.member.voice.channel.id,
      guildId: message.guild.id,
      adapterCreator: message.guild.voiceAdapterCreator,
    });

    message.reply('Joined your voice channel! 🎵');
  }

  if (message.content === '!leave') {
    const connection = joinVoiceChannel({
      channelId: message.member.voice.channel?.id,
      guildId: message.guild.id,
      adapterCreator: message.guild.voiceAdapterCreator,
    });
    
    if (connection) {
      connection.destroy();
      message.reply('Left the voice channel! 👋');
    }
  }

  if (message.content.startsWith('!tts ')) {
    if (!message.member.voice.channel) {
      return message.reply('You need to be in a voice channel to use TTS!');
    }

    const text = message.content.slice(5);
    
    if (!text) {
      return message.reply('Please provide text! Example: `!tts Hello everyone`');
    }

    const fileName = `tts-${Date.now()}.mp3`;
    const filePath = path.join(__dirname, fileName);

    gtts.save(filePath, text, (err) => {
      if (err) {
        return message.reply('Error generating TTS 😢');
      }

      const connection = joinVoiceChannel({
        channelId: message.member.voice.channel.id,
        guildId: message.guild.id,
        adapterCreator: message.guild.voiceAdapterCreator,
      });

      const player = createAudioPlayer();
      const resource = createAudioResource(filePath);

      player.play(resource);
      connection.subscribe(player);

      message.reply(`🔊 Playing: "${text}"`);

      player.on('stateChange', (oldState, newState) => {
        if (newState.status === 'idle') {
          fs.unlinkSync(filePath);
        }
      });
    });
  }

  // ===== INFO COMMANDS =====
  if (message.content === '!serverinfo') {
    const embed = new EmbedBuilder()
      .setColor(0x0099ff)
      .setTitle(message.guild.name)
      .setThumbnail(message.guild.iconURL())
      .addFields(
        { name: '👥 Members', value: `${message.guild.memberCount}`, inline: true },
        { name: '📅 Created', value: message.guild.createdAt.toDateString(), inline: true },
        { name: '🆔 Server ID', value: message.guild.id, inline: true }
      )
      .setTimestamp();

    message.reply({ embeds: [embed] });
  }

  if (message.content === '!userinfo') {
    const user = message.author;
    const embed = new EmbedBuilder()
      .setColor(0x00ff00)
      .setTitle('User Information')
      .setThumbnail(user.displayAvatarURL())
      .addFields(
        { name: '👤 Username', value: user.username, inline: true },
        { name: '🆔 User ID', value: user.id, inline: true },
        { name: '📅 Account Created', value: user.createdAt.toDateString(), inline: false }
      );

    message.reply({ embeds: [embed] });
  }

  // ===== FUN COMMANDS =====
  if (message.content === '!roll') {
    const roll = Math.floor(Math.random() * 6) + 1;
    message.reply(`🎲 You rolled a **${roll}**!`);
  }

  if (message.content === '!flip') {
    const result = Math.random() < 0.5 ? 'Heads' : 'Tails';
    message.reply(`🪙 The coin landed on **${result}**!`);
  }

  if (message.content === '!8ball') {
    const responses = [
      'Yes, definitely!', 'No way!', 'Maybe...', 'Ask again later',
      'Absolutely!', 'I doubt it', 'Signs point to yes', 'Very doubtful'
    ];
    const answer = responses[Math.floor(Math.random() * responses.length)];
    message.reply(`🎱 ${answer}`);
  }

  // ===== YOUTUBE COMMANDS =====
  if (message.content === '!checkvideos') {
    message.reply('Checking for new PippyOC videos... 🔍');
    await checkForNewVideos();
  }

  if (message.content === '!setchannel') {
    if (!message.member.permissions.has('Administrator')) {
      return message.reply('You need administrator permissions to use this command!');
    }
    message.reply(`Set this channel (${message.channel.name}) as the notification channel in the code!`);
  }

  // ===== HELP COMMAND =====
  if (message.content === '!help') {
    const embed = new EmbedBuilder()
      .setColor(0x9B59B6)
      .setTitle('📋 Bot Commands')
      .setDescription('Here are all available commands:')
      .addFields(
        { name: '🎤 Voice Commands', value: '`!join` - Join voice channel\n`!leave` - Leave voice channel\n`!tts <text>` - Text-to-speech' },
        { name: 'ℹ️ Info Commands', value: '`!serverinfo` - Server details\n`!userinfo` - Your user info\n`!ping` - Check latency' },
        { name: '🎮 Fun Commands', value: '`!roll` - Roll a dice\n`!flip` - Flip a coin\n`!8ball` - Ask the magic 8-ball' },
        { name: '📺 YouTube Commands', value: '`!checkvideos` - Manually check for new videos' },
        { name: '⚙️ Other', value: '`!hello` - Say hello\n`!help` - Show this message' }
      )
      .setFooter({ text: 'Use ! before each command' });

    message.reply({ embeds: [embed] });
  }
});

// Login
client.login(process.env.TOKEN);