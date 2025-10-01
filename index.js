const { Client, GatewayIntentBits, EmbedBuilder, REST, Routes, SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const express = require('express');
const Parser = require('rss-parser');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Data persistence
const DATA_FILE = path.join(__dirname, 'botdata.json');
let botData = {
  levels: {},
  economy: {},
  warnings: {},
  lastVideoId: ''
};

// ADD THIS HERE (after botData)
const automodConfig = {
  enabled: true,
  logChannelId: process.env.AUTOMOD_LOG_CHANNEL,
  warnThreshold: 3,
  timeoutDuration: 60
};

function checkForInappropriateContent(content) {
  const normalized = content.toLowerCase()
    .replace(/\s+/g, '')
    .replace(/[^a-z0-9]/g, '')
    .replace(/0/g, 'o')
    .replace(/1/g, 'i')
    .replace(/3/g, 'e')
    .replace(/4/g, 'a')
    .replace(/5/g, 's')
    .replace(/7/g, 't')
    .replace(/8/g, 'b');
  
  const blockedPatterns = [
    /n[i1l!|]+[g9q]+[e3a@]+r/i,
    /n[i1l!|]+[g9q]+[a@4]+/i,
    /f[a@4]+[g9q]+[g9q]?[o0]+[t7]/i,
    /r[e3]+[t7]+[a@4]+r?d/i,
    /k[i1l!|]+k[e3]+/i,
  ];
  
  return blockedPatterns.some(pattern => pattern.test(normalized));
}

// Load data on startup
function loadData() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      botData = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
    }
  } catch (error) {
    console.error('Error loading data:', error);
  }
}

// Save data
function saveData() {
  try {
    fs.writeFileSync(DATA_FILE, JSON.stringify(botData, null, 2));
  } catch (error) {
    console.error('Error saving data:', error);
  }
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildModeration,
  ],
});

app.get('/', (req, res) => {
  res.send('Bot is running!');
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

// Welcome messages
client.on('guildMemberAdd', member => {
  if (member.user.bot) return;

  const welcomeMessage = `
👋 Welcome to **${member.guild.name}**, ${member.user.username}!

I'm Tooly Bot! Here's what I can do:
• 📊 Earn XP and level up by chatting
• 💰 Economy system with daily rewards
• 🎮 Fun commands and games
• 🛡️ Moderation tools

Use \`/help\` to see all commands!
`;

  member.send(welcomeMessage).catch(err => {
    console.log(`Could not send DM to ${member.user.tag}`);
  });
});

// YouTube RSS Check
const parser = new Parser();
const YOUTUBE_CHANNEL_ID = process.env.YOUTUBE_CHANNEL_ID;
const NOTIFICATION_CHANNEL_ID = process.env.NOTIFICATION_CHANNEL_ID;

async function checkForNewVideos() {
  if (!YOUTUBE_CHANNEL_ID || !NOTIFICATION_CHANNEL_ID) return;
  
  try {
    const feedUrl = `https://www.youtube.com/feeds/videos.xml?channel_id=${YOUTUBE_CHANNEL_ID}`;
    const feed = await parser.parseURL(feedUrl);
    
    if (feed.items && feed.items.length > 0) {
      const latestVideo = feed.items[0];
      
      if (latestVideo.id !== botData.lastVideoId && botData.lastVideoId !== '') {
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
            content: '📺 New video alert!',
            embeds: [embed] 
          });
        }
      }
      
      botData.lastVideoId = latestVideo.id;
      saveData();
    }
  } catch (error) {
    console.error('Error checking for new videos:', error);
  }
}

// Level system functions
function addXP(userId) {
  if (!botData.levels[userId]) {
    botData.levels[userId] = { xp: 0, level: 1, lastMessage: 0 };
  }
  
  const now = Date.now();
  const userData = botData.levels[userId];
  
  // Cooldown: 1 message per minute for XP
  if (now - userData.lastMessage < 60000) return null;
  
  userData.lastMessage = now;
  const xpGain = Math.floor(Math.random() * 15) + 10; // 10-25 XP
  userData.xp += xpGain;
  
  // Level up calculation
  const xpNeeded = userData.level * 100;
  if (userData.xp >= xpNeeded) {
    userData.level++;
    userData.xp = 0;
    saveData();
    return userData.level;
  }
  
  saveData();
  return null;
}

function getLeaderboard(limit = 10) {
  return Object.entries(botData.levels)
    .sort((a, b) => {
      if (b[1].level !== a[1].level) return b[1].level - a[1].level;
      return b[1].xp - a[1].xp;
    })
    .slice(0, limit);
}

// Economy functions
function getCoins(userId) {
  if (!botData.economy[userId]) {
    botData.economy[userId] = { coins: 0, bank: 0, lastDaily: 0 };
  }
  return botData.economy[userId];
}

function addCoins(userId, amount) {
  const userData = getCoins(userId);
  userData.coins += amount;
  saveData();
}

// Commands
const commands = [
  // Info
  new SlashCommandBuilder().setName('hello').setDescription('Say hello'),
  new SlashCommandBuilder().setName('ping').setDescription('Check bot latency'),
  new SlashCommandBuilder().setName('serverinfo').setDescription('Show server information'),
  new SlashCommandBuilder().setName('userinfo').setDescription('Show user information')
    .addUserOption(option => option.setName('user').setDescription('User to check').setRequired(false)),
  new SlashCommandBuilder().setName('help').setDescription('Show all commands'),
  
  // Fun
  new SlashCommandBuilder().setName('roll').setDescription('Roll a dice'),
  new SlashCommandBuilder().setName('flip').setDescription('Flip a coin'),
  new SlashCommandBuilder().setName('8ball').setDescription('Ask the magic 8-ball')
    .addStringOption(option => option.setName('question').setDescription('Your question').setRequired(true)),
  new SlashCommandBuilder().setName('kitty').setDescription('Get a random cat picture'),
  new SlashCommandBuilder().setName('joke').setDescription('Get a random joke'),
  new SlashCommandBuilder().setName('yotsuba').setDescription('Yotsuba picture'),

  // Levels
  new SlashCommandBuilder().setName('rank').setDescription('Check your rank and level')
    .addUserOption(option => option.setName('user').setDescription('User to check').setRequired(false)),
  new SlashCommandBuilder().setName('leaderboard').setDescription('View the server leaderboard'),
  
  // Economy
  new SlashCommandBuilder().setName('balance').setDescription('Check your balance')
    .addUserOption(option => option.setName('user').setDescription('User to check').setRequired(false)),
  new SlashCommandBuilder().setName('daily').setDescription('Claim your daily coins'),
  new SlashCommandBuilder().setName('work').setDescription('Work for coins'),
  new SlashCommandBuilder().setName('deposit').setDescription('Deposit coins to bank')
    .addIntegerOption(option => option.setName('amount').setDescription('Amount to deposit').setRequired(true)),
  new SlashCommandBuilder().setName('withdraw').setDescription('Withdraw coins from bank')
    .addIntegerOption(option => option.setName('amount').setDescription('Amount to withdraw').setRequired(true)),
  new SlashCommandBuilder().setName('give').setDescription('Give coins to someone')
    .addUserOption(option => option.setName('user').setDescription('User to give coins').setRequired(true))
    .addIntegerOption(option => option.setName('amount').setDescription('Amount to give').setRequired(true)),
  
  // Moderation
  new SlashCommandBuilder().setName('warn').setDescription('Warn a user (Mod only)')
    .addUserOption(option => option.setName('user').setDescription('User to warn').setRequired(true))
    .addStringOption(option => option.setName('reason').setDescription('Reason').setRequired(true))
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers),
  new SlashCommandBuilder().setName('warnings').setDescription('Check warnings')
    .addUserOption(option => option.setName('user').setDescription('User to check').setRequired(false))
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers),
  new SlashCommandBuilder().setName('kick').setDescription('Kick a user')
    .addUserOption(option => option.setName('user').setDescription('User to kick').setRequired(true))
    .addStringOption(option => option.setName('reason').setDescription('Reason').setRequired(false))
    .setDefaultMemberPermissions(PermissionFlagsBits.KickMembers),
  new SlashCommandBuilder().setName('ban').setDescription('Ban a user')
    .addUserOption(option => option.setName('user').setDescription('User to ban').setRequired(true))
    .addStringOption(option => option.setName('reason').setDescription('Reason').setRequired(false))
    .setDefaultMemberPermissions(PermissionFlagsBits.BanMembers),
  new SlashCommandBuilder().setName('timeout').setDescription('Timeout a user')
    .addUserOption(option => option.setName('user').setDescription('User to timeout').setRequired(true))
    .addIntegerOption(option => option.setName('duration').setDescription('Duration in minutes').setRequired(true))
    .addStringOption(option => option.setName('reason').setDescription('Reason').setRequired(false))
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers),
  new SlashCommandBuilder().setName('purge').setDescription('Delete messages')
    .addIntegerOption(option => option.setName('amount').setDescription('Number of messages (1-100)').setRequired(true))
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages),
  
  // Admin
  new SlashCommandBuilder().setName('say').setDescription('Make the bot say something (Admin only)')
    .addStringOption(option => option.setName('message').setDescription('Message to send').setRequired(true))
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
  new SlashCommandBuilder().setName('embed').setDescription('Send an embed message (Admin only)')
    .addStringOption(option => option.setName('text').setDescription('Embed text').setRequired(true))
    .addStringOption(option => option.setName('image').setDescription('Image URL').setRequired(false))
    .addStringOption(option => option.setName('color').setDescription('Hex color (e.g., #FF0000)').setRequired(false))
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
  new SlashCommandBuilder().setName('dm').setDescription('Send a DM to a user (Mod only)')
    .addUserOption(option => option.setName('user').setDescription('User to message').setRequired(true))
    .addStringOption(option => option.setName('message').setDescription('Message content').setRequired(true))
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers),
  
  // YouTube
  new SlashCommandBuilder().setName('checkvideos').setDescription('Check for new PippyOC videos (Mod only)')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
 
];

client.once('ready', async () => {
  console.log(`Logged in as ${client.user.tag}!`);
  loadData();
  
  const rest = new REST({ version: '10' }).setToken(process.env.TOKEN);
  
  try {
    console.log('Registering slash commands...');
    const commandsJson = commands.map(command => command.toJSON());
    await rest.put(Routes.applicationCommands(client.user.id), { body: commandsJson });
    console.log('Slash commands registered!');
  } catch (error) {
    console.error('Error registering commands:', error);
  }
  
  if (YOUTUBE_CHANNEL_ID && NOTIFICATION_CHANNEL_ID) {
    checkForNewVideos();
    setInterval(checkForNewVideos, 300000);
  }
  
  // Auto-save every 5 minutes
  setInterval(saveData, 300000);
});

client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;

  const { commandName } = interaction;

  try {
    // Info commands
    if (commandName === 'hello') {
      await interaction.reply('Hello! 👋 I\'m Tooly Bot!');
    }

    if (commandName === 'ping') {
      await interaction.reply(`🏓 Pong! Latency: ${client.ws.ping}ms`);
    }

    if (commandName === 'serverinfo') {
      const embed = new EmbedBuilder()
        .setColor(0x9B59B6)
        .setTitle(interaction.guild.name)
        .setThumbnail(interaction.guild.iconURL())
        .addFields(
          { name: '👥 Members', value: `${interaction.guild.memberCount}`, inline: true },
          { name: '📅 Created', value: interaction.guild.createdAt.toDateString(), inline: true },
          { name: '🆔 Server ID', value: interaction.guild.id, inline: true },
          { name: '👑 Owner', value: `<@${interaction.guild.ownerId}>`, inline: true }
        )
        .setTimestamp();

      await interaction.reply({ embeds: [embed] });
    }

    if (commandName === 'userinfo') {
      const user = interaction.options.getUser('user') || interaction.user;
      const member = interaction.guild.members.cache.get(user.id);
      
      const embed = new EmbedBuilder()
        .setColor(0x9B59B6)
        .setTitle('User Information')
        .setThumbnail(user.displayAvatarURL())
        .addFields(
          { name: '👤 Username', value: user.username, inline: true },
          { name: '🆔 User ID', value: user.id, inline: true },
          { name: '📅 Account Created', value: user.createdAt.toDateString(), inline: false }
        );
      
      if (member) {
        embed.addFields(
          { name: '📥 Joined Server', value: member.joinedAt.toDateString(), inline: false }
        );
      }

      await interaction.reply({ embeds: [embed] });
    }

    // Fun commands
    if (commandName === 'roll') {
      const roll = Math.floor(Math.random() * 6) + 1;
      await interaction.reply(`🎲 You rolled a **${roll}**!`);
    }

    if (commandName === 'flip') {
      const result = Math.random() < 0.5 ? 'Heads' : 'Tails';
      await interaction.reply(`🪙 The coin landed on **${result}**!`);
    }

    if (commandName === '8ball') {
      const question = interaction.options.getString('question').slice(0, 200);
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
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        
        const response = await fetch('https://api.thecatapi.com/v1/images/search', {
          signal: controller.signal
        });
        clearTimeout(timeout);
        
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
    
    if (commandName === 'yotsuba') {
      const embed = new EmbedBuilder()
        .setColor(0x77DD77)
        .setTitle('🍀 Yotsuba!')
        .setImage('https://i.ibb.co/BDhQV8B/yotsuba.jpg')
        .setDescription('Here\'s a Yotsuba image!')
        .setTimestamp();

      await interaction.reply({ embeds: [embed] });
    }

    if (commandName === 'joke') {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        
        const response = await fetch('https://official-joke-api.appspot.com/random_joke', {
          signal: controller.signal
        });
        clearTimeout(timeout);
        
        const data = await response.json();
        
        const embed = new EmbedBuilder()
          .setColor(0xFFA500)
          .setTitle('😂 Random Joke')
          .setDescription(`**${data.setup}**\n\n||${data.punchline}||`)
          .setFooter({ text: `${data.type} joke` })
          .setTimestamp();
        
        await interaction.reply({ embeds: [embed] });
      } catch (error) {
        // Fallback to local jokes if API fails
        const jokes = [
          { setup: 'Why did the scarecrow win an award?', punchline: 'Because he was outstanding in his field!' },
          { setup: 'Why don\'t scientists trust atoms?', punchline: 'Because they make up everything!' },
          { setup: 'What do you call a fake noodle?', punchline: 'An impasta!' },
          { setup: 'Why did the bicycle fall over?', punchline: 'Because it was two tired!' },
          { setup: 'What did the ocean say to the beach?', punchline: 'Nothing, it just waved!' },
          { setup: 'Why do programmers prefer dark mode?', punchline: 'Because light attracts bugs!' },
          { setup: 'What\'s a computer\'s favorite snack?', punchline: 'Microchips!' },
          { setup: 'Why was the math book sad?', punchline: 'Because it had too many problems!' },
        ];
        
        const joke = jokes[Math.floor(Math.random() * jokes.length)];
        
        const embed = new EmbedBuilder()
          .setColor(0xFFA500)
          .setTitle('😂 Random Joke')
          .setDescription(`**${joke.setup}**\n\n||${joke.punchline}||`)
          .setTimestamp();
        
        await interaction.reply({ embeds: [embed] });
      }
    }

    // Level commands
    if (commandName === 'rank') {
      const user = interaction.options.getUser('user') || interaction.user;
      const userData = botData.levels[user.id] || { xp: 0, level: 1 };
      const xpNeeded = userData.level * 100;
      
      const leaderboard = getLeaderboard(100);
      const rank = leaderboard.findIndex(([id]) => id === user.id) + 1;
      
      const embed = new EmbedBuilder()
        .setColor(0x9B59B6)
        .setTitle(`📊 ${user.username}'s Rank`)
        .setThumbnail(user.displayAvatarURL())
        .addFields(
          { name: '🏆 Rank', value: `#${rank || 'Unranked'}`, inline: true },
          { name: '⭐ Level', value: `${userData.level}`, inline: true },
          { name: '✨ XP', value: `${userData.xp}/${xpNeeded}`, inline: true }
        )
        .setTimestamp();
      
      await interaction.reply({ embeds: [embed] });
    }

    if (commandName === 'leaderboard') {
      const leaderboard = getLeaderboard(10);
      
      if (leaderboard.length === 0) {
        return interaction.reply('No one has earned XP yet!');
      }
      
      const description = leaderboard.map(([userId, data], index) => {
        const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `**${index + 1}.**`;
        return `${medal} <@${userId}> - Level ${data.level} (${data.xp} XP)`;
      }).join('\n');
      
      const embed = new EmbedBuilder()
        .setColor(0x9B59B6)
        .setTitle('🏆 Server Leaderboard')
        .setDescription(description)
        .setTimestamp();
      
      await interaction.reply({ embeds: [embed] });
    }

    // Economy commands
    if (commandName === 'balance') {
      const user = interaction.options.getUser('user') || interaction.user;
      const userData = getCoins(user.id);
      
      const embed = new EmbedBuilder()
        .setColor(0xFFD700)
        .setTitle(`💰 ${user.username}'s Balance`)
        .addFields(
          { name: '🪙 Wallet', value: `${userData.coins} coins`, inline: true },
          { name: '🏦 Bank', value: `${userData.bank} coins`, inline: true },
          { name: '💵 Total', value: `${userData.coins + userData.bank} coins`, inline: true }
        )
        .setTimestamp();
      
      await interaction.reply({ embeds: [embed] });
    }

    if (commandName === 'daily') {
      const userData = getCoins(interaction.user.id);
      const now = Date.now();
      const cooldown = 86400000; // 24 hours
      
      if (now - userData.lastDaily < cooldown) {
        const timeLeft = cooldown - (now - userData.lastDaily);
        const hours = Math.floor(timeLeft / 3600000);
        const minutes = Math.floor((timeLeft % 3600000) / 60000);
        return interaction.reply(`⏳ You already claimed your daily! Come back in ${hours}h ${minutes}m`);
      }
      
      const amount = Math.floor(Math.random() * 500) + 500; // 500-1000
      userData.coins += amount;
      userData.lastDaily = now;
      saveData();
      
      await interaction.reply(`✅ You claimed your daily reward of **${amount} coins**! 💰`);
    }

    if (commandName === 'work') {
      const amount = Math.floor(Math.random() * 200) + 100; // 100-300
      addCoins(interaction.user.id, amount);
      
      const jobs = [
        'worked at a cafe', 'delivered pizzas', 'coded a website',
        'walked dogs', 'mowed lawns', 'streamed on Twitch'
      ];
      const job = jobs[Math.floor(Math.random() * jobs.length)];
      
      await interaction.reply(`💼 You ${job} and earned **${amount} coins**!`);
    }

    if (commandName === 'deposit') {
      const amount = interaction.options.getInteger('amount');
      const userData = getCoins(interaction.user.id);
      
      if (amount < 1) {
        return interaction.reply('❌ Amount must be positive!');
      }
      
      if (amount > userData.coins) {
        return interaction.reply('❌ You don\'t have enough coins!');
      }
      
      userData.coins -= amount;
      userData.bank += amount;
      saveData();
      
      await interaction.reply(`✅ Deposited **${amount} coins** to your bank!`);
    }
    
    if (commandName === 'withdraw') {
      const amount = interaction.options.getInteger('amount');
      const userData = getCoins(interaction.user.id);
      
      if (amount < 1) {
        return interaction.reply('❌ Amount must be positive!');
      }
      
      if (amount > userData.bank) {
        return interaction.reply('❌ You don\'t have enough coins in your bank!');
      }
      
      userData.bank -= amount;
      userData.coins += amount;
      saveData();
      
      await interaction.reply(`✅ Withdrew **${amount} coins** from your bank!`);
    }

    if (commandName === 'give') {
      const recipient = interaction.options.getUser('user');
      const amount = interaction.options.getInteger('amount');
      
      if (recipient.bot) {
        return interaction.reply('❌ You can\'t give coins to bots!');
      }
      
      if (recipient.id === interaction.user.id) {
        return interaction.reply('❌ You can\'t give coins to yourself!');
      }
      
      if (amount < 1) {
        return interaction.reply('❌ Amount must be positive!');
      }
      
      const userData = getCoins(interaction.user.id);
      
      if (amount > userData.coins) {
        return interaction.reply('❌ You don\'t have enough coins!');
      }
      
      // Actually transfer coins
      userData.coins -= amount;
      const recipientData = getCoins(recipient.id);
      recipientData.coins += amount;
      saveData();
      
      return interaction.reply(`✅ Gave **${amount} coins** to ${recipient.username}!`);
    }
    
    if (commandName === 'warn') {
      const user = interaction.options.getUser('user');
      const reason = interaction.options.getString('reason').slice(0, 500);
      
      if (user.bot) {
        return interaction.reply({ content: '❌ Cannot warn bots!', ephemeral: true });
      }
      
      if (!botData.warnings[user.id]) {
        botData.warnings[user.id] = [];
      }
      
      botData.warnings[user.id].push({
        reason,
        mod: interaction.user.id,
        timestamp: Date.now()
      });
      saveData();
      
      try {
        await user.send(`⚠️ You have been warned in **${interaction.guild.name}**\n**Reason:** ${reason}`);
      } catch (e) {
        // User has DMs off
      }
      
      await interaction.reply(`✅ Warned ${user.username} for: ${reason}`);
    }

    if (commandName === 'warnings') {
      const user = interaction.options.getUser('user') || interaction.user;
      const warnings = botData.warnings[user.id] || [];
      
      if (warnings.length === 0) {
        return interaction.reply(`${user.username} has no warnings!`);
      }
      
      const description = warnings.map((w, i) => {
        const date = new Date(w.timestamp).toLocaleDateString();
        return `**${i + 1}.** ${w.reason}\nBy: <@${w.mod}> on ${date}`;
      }).join('\n\n');
      
      const embed = new EmbedBuilder()
        .setColor(0xFF0000)
        .setTitle(`⚠️ ${user.username}'s Warnings (${warnings.length})`)
        .setDescription(description)
        .setTimestamp();
      
      await interaction.reply({ embeds: [embed] });
    }

    if (commandName === 'kick') {
      const user = interaction.options.getUser('user');
      const reason = interaction.options.getString('reason') || 'No reason provided';
      const member = interaction.guild.members.cache.get(user.id);
      
      if (!member) {
        return interaction.reply({ content: '❌ User not found!', ephemeral: true });
      }
      
      if (!member.kickable) {
        return interaction.reply({ content: '❌ Cannot kick this user!', ephemeral: true });
      }
      
      await member.kick(reason);
      await interaction.reply(`✅ Kicked ${user.username} for: ${reason}`);
    }

    if (commandName === 'ban') {
      const user = interaction.options.getUser('user');
      const reason = interaction.options.getString('reason') || 'No reason provided';
      const member = interaction.guild.members.cache.get(user.id);
      
      if (!member) {
        return interaction.reply({ content: '❌ User not found!', ephemeral: true });
      }
      
      if (!member.bannable) {
        return interaction.reply({ content: '❌ Cannot ban this user!', ephemeral: true });
      }
      
      await member.ban({ reason });
      await interaction.reply(`✅ Banned ${user.username} for: ${reason}`);
    }

    if (commandName === 'timeout') {
      const user = interaction.options.getUser('user');
      const duration = interaction.options.getInteger('duration');
      const reason = interaction.options.getString('reason') || 'No reason provided';
      const member = interaction.guild.members.cache.get(user.id);
      
      if (!member) {
        return interaction.reply({ content: '❌ User not found!', ephemeral: true });
      }
      
      if (duration < 1 || duration > 40320) { // Max 28 days
        return interaction.reply({ content: '❌ Duration must be between 1 and 40320 minutes!', ephemeral: true });
      }
      
      await member.timeout(duration * 60000, reason);
      await interaction.reply(`✅ Timed out ${user.username} for ${duration} minutes. Reason: ${reason}`);
    }

    if (commandName === 'purge') {
      const amount = interaction.options.getInteger('amount');
      
      if (amount < 1 || amount > 100) {
        return interaction.reply({ content: '❌ Amount must be between 1 and 100!', ephemeral: true });
      }
      
      const deleted = await interaction.channel.bulkDelete(amount, true);
      await interaction.reply({ content: `✅ Deleted ${deleted.size} messages!`, ephemeral: true });
    }

    // Admin commands
    if (commandName === 'say') {
      const text = interaction.options.getString('message').slice(0, 2000);
      await interaction.deferReply({ ephemeral: true });
      await interaction.channel.send(text);
      await interaction.editReply('✅ Message sent!');
    }

    if (commandName === 'embed') {
      const text = interaction.options.getString('text').slice(0, 4096);
      const imageUrl = interaction.options.getString('image');
      const colorHex = interaction.options.getString('color') || '#9B59B6';
      
      if (!/^#[0-9A-F]{6}$/i.test(colorHex)) {
        return interaction.reply({ content: '❌ Invalid hex color!', ephemeral: true });
      }
      
      const colorInt = parseInt(colorHex.replace('#', ''), 16);
      
      const embed = new EmbedBuilder()
        .setColor(colorInt)
        .setDescription(text)
        .setTimestamp();
      
      if (imageUrl) {
        if (!/^https?:\/\/.+\.(jpg|jpeg|png|gif|webp)$/i.test(imageUrl)) {
          return interaction.reply({ content: '❌ Invalid image URL!', ephemeral: true });
        }
        embed.setImage(imageUrl);
      }
      
      await interaction.deferReply({ ephemeral: true });
      await interaction.channel.send({ embeds: [embed] });
      await interaction.editReply('✅ Embed sent!');
    }

    if (commandName === 'dm') {
      const targetUser = interaction.options.getUser('user');
      const message = interaction.options.getString('message').slice(0, 2000);

      try {
        await targetUser.send(`📬 **Message from ${interaction.guild.name} Mod Team:**\n\n${message}`);
        await interaction.reply({ content: `✅ Message sent to ${targetUser.tag}`, ephemeral: true });
      } catch (error) {
        await interaction.reply({ content: `❌ Could not send DM. The user may have DMs off.`, ephemeral: true });
      }
    }

    // YouTube
    if (commandName === 'checkvideos') {
      await interaction.reply('Checking for new PippyOC videos... 🔍');
      await checkForNewVideos();
    }

    // Help command
    if (commandName === 'help') {
      const embed = new EmbedBuilder()
        .setColor(0x9B59B6)
        .setTitle('📋 Tooly Bot Commands')
        .setDescription('Here are all my commands organized by category!')
        .addFields(
          { 
            name: 'ℹ️ Info', 
            value: '`/hello` `/ping` `/serverinfo` `/userinfo` `/help`',
            inline: false
          },
          { 
            name: '🎮 Fun', 
            value: '`/roll` `/flip` `/8ball` `/kitty` `/joke`',
            inline: false
          },
          { 
            name: '📊 Levels', 
            value: '`/rank` `/leaderboard`\nEarn XP by chatting! (1 msg/min)',
            inline: false
          },
          { 
            name: '💰 Economy', 
            value: '`/balance` `/daily` `/work` `/deposit` `/withdraw` `/give`',
            inline: false
          },
          { 
            name: '🛡️ Moderation', 
            value: '`/warn` `/warnings` `/kick` `/ban` `/timeout` `/purge`',
            inline: false
          },
          { 
            name: '👑 Admin', 
            value: '`/say` `/embed` `/dm`',
            inline: false
          },
          { 
            name: '📺 YouTube', 
            value: '`/checkvideos` - Check for new PippyOC videos',
            inline: false
          }
        )
        .setFooter({ text: 'Type / to see all commands!' })
        .setTimestamp();

      await interaction.reply({ embeds: [embed] });
    }

  } catch (error) {
    console.error(`Error handling command ${commandName}:`, error);
    const errorMsg = '❌ An error occurred while executing this command!';
    
    if (interaction.replied || interaction.deferred) {
      await interaction.followUp({ content: errorMsg, ephemeral: true }).catch(() => {});
    } else {
      await interaction.reply({ content: errorMsg, ephemeral: true }).catch(() => {});
    }
  }
});

// Move this block OUTSIDE of the interactionCreate handler!
// It should NOT be inside the interactionCreate event.
client.on('messageCreate', async (message) => {
  if (message.author.bot || !message.guild) return;

  // ADD AUTOMOD CHECK HERE (before XP system)
  if (automodConfig.enabled) {
    if (checkForInappropriateContent(message.content)) {
      try {
        await message.delete();
        
        if (!botData.warnings[message.author.id]) {
          botData.warnings[message.author.id] = [];
        }
        
        botData.warnings[message.author.id].push({
          reason: 'Automod: Inappropriate language detected',
          mod: client.user.id,
          timestamp: Date.now()
        });
        saveData();
        
        const warningCount = botData.warnings[message.author.id].length;
        
        const warningMsg = await message.channel.send(
          `⚠️ ${message.author}, your message was removed for inappropriate content. Warning ${warningCount}/${automodConfig.warnThreshold}`
        );
        
        setTimeout(() => warningMsg.delete().catch(() => {}), 5000);
        
        if (warningCount >= automodConfig.warnThreshold) {
          const member = message.guild.members.cache.get(message.author.id);
          if (member && member.moderatable) {
            await member.timeout(
              automodConfig.timeoutDuration * 60000,
              `Automod: ${automodConfig.warnThreshold} warnings reached`
            );
            
            await message.channel.send(
              `🔇 ${message.author} has been timed out for ${automodConfig.timeoutDuration} minutes due to repeated violations.`
            );
          }
        }
        
        if (automodConfig.logChannelId) {
          const logChannel = client.channels.cache.get(automodConfig.logChannelId);
          if (logChannel) {
            const logEmbed = new EmbedBuilder()
              .setColor(0xFF0000)
              .setTitle('🛡️ Automod Action')
              .addFields(
                { name: 'User', value: `${message.author.tag} (${message.author.id})`, inline: true },
                { name: 'Channel', value: `${message.channel}`, inline: true },
                { name: 'Content', value: `||${message.content.slice(0, 200)}||`, inline: false },
                { name: 'Warnings', value: `${warningCount}/${automodConfig.warnThreshold}`, inline: true }
              )
              .setTimestamp();
            
            await logChannel.send({ embeds: [logEmbed] });
          }
        }
        
        return;
      } catch (error) {
        console.error('Automod error:', error);
      }
    }
  }

  // Add XP for messages
  const newLevel = addXP(message.author.id);
  
  if (newLevel) {
    const levelUpMessages = [
      `🎉 GG ${message.author}! You leveled up to **Level ${newLevel}**!`,
      `⭐ Congrats ${message.author}! You're now **Level ${newLevel}**!`,
      `🚀 Level up! ${message.author} reached **Level ${newLevel}**!`,
      `💫 Awesome! ${message.author} is now **Level ${newLevel}**!`
    ];
    
    const randomMsg = levelUpMessages[Math.floor(Math.random() * levelUpMessages.length)];
    
    // Give coins on level up
    const coinReward = newLevel * 50;
    addCoins(message.author.id, coinReward);
    
    message.channel.send(`${randomMsg} You earned **${coinReward} coins**! 💰`);
  }

  // Name detection - responds when "tooly" or "toolybot" is mentioned in message
  const content = message.content.toLowerCase();
  const namePatterns = ['tooly', 'toolybot', 'tooly bot'];
  const mentionsTooly = namePatterns.some(pattern => content.includes(pattern));
  
  if (mentionsTooly && !message.content.startsWith('/')) {
    // Random responses when name is mentioned
    const responses = [
      'Yes? You called? 👀',
      'Tooly reporting for duty! 🫡',
      'Hey there! Need something? Use `/help` to see what I can do!',
      'That\'s me! How can I help? 😊',
      'You rang? 🔔',
      'Hi! I\'m here! Type `/help` for commands! 👋',
      'Tooly at your service! ⚡',
      'Yep, I\'m listening! 👂',
      'Someone say my name? 🤖',
      'What\'s up? Need help? Try `/help`! 💬'
    ];
    
    const randomResponse = responses[Math.floor(Math.random() * responses.length)];
    
    // Small cooldown to prevent spam (per user, per channel)
    const cooldownKey = `${message.author.id}-${message.channel.id}`;
    if (!client.nameMentionCooldowns) client.nameMentionCooldowns = new Map();
    
    const now = Date.now();
    const cooldownAmount = 30000; // 30 seconds
    
    if (client.nameMentionCooldowns.has(cooldownKey)) {
      const expirationTime = client.nameMentionCooldowns.get(cooldownKey) + cooldownAmount;
      if (now < expirationTime) {
        return; // Still in cooldown, ignore
      }
    }
    
    client.nameMentionCooldowns.set(cooldownKey, now);
    
    // Clean up old cooldowns every 5 minutes
    setTimeout(() => {
      for (const [key, timestamp] of client.nameMentionCooldowns.entries()) {
        if (now - timestamp > cooldownAmount) {
          client.nameMentionCooldowns.delete(key);
        }
      }
    }, 300000);
    
    return message.reply(randomResponse);
  }

  // Mention handler for legacy commands
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
    
    if (command === 'joke') {
      const jokes = [
        { setup: 'Why did the scarecrow win an award?', punchline: 'Because he was outstanding in his field!' },
        { setup: 'Why don\'t scientists trust atoms?', punchline: 'Because they make up everything!' },
        { setup: 'What do you call a fake noodle?', punchline: 'An impasta!' },
      ];
      const joke = jokes[Math.floor(Math.random() * jokes.length)];
      return message.reply(`😂 **${joke.setup}**\n||${joke.punchline}||`);
    }
    
    if (command === 'help' || !command) {
      const embed = new EmbedBuilder()
        .setColor(0x9B59B6)
        .setTitle('📋 Tooly Bot Commands')
        .setDescription('Use `/help` to see all commands!\n\nFeatures:\n• 📊 Level system - Chat to earn XP\n• 💰 Economy - Daily rewards & work\n• 🛡️ Moderation tools\n• 🎮 Fun commands')
        .setFooter({ text: 'Type / to see all slash commands!' });
      
      return message.reply({ embeds: [embed] });
    }
  }

  // DM relay logic
  if (message.channel.type === 1 && !message.author.bot) { // type 1 = DM
    // Relay DM to log channel
    if (DM_LOG_CHANNEL_ID) {
      const logChannel = client.channels.cache.get(DM_LOG_CHANNEL_ID);
      if (logChannel) {
        const embed = new EmbedBuilder()
          .setColor(0x3498DB)
          .setTitle('📩 New DM Received')
          .setDescription(message.content)
          .setFooter({ text: `From: ${message.author.tag} (${message.author.id})` })
          .setTimestamp();
        await logChannel.send({ embeds: [embed] });
      }
    }

    // Basic AI reply (Mee6 style)
    const content = message.content.toLowerCase();
    if (content.includes('hi tooly') || content.includes('hello tooly')) {
      await message.reply('Hi! 👋');
    } else if (content.includes('how are you')) {
      await message.reply('I\'m just a bot, but I\'m doing great! 😊');
    } else if (content.includes('help')) {
      await message.reply('Need help? Type `/help` in a server for my commands!');
    }
    // Add more simple triggers here if you want
    return;
  }
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('Saving data and shutting down...');
  saveData();
  client.destroy();
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('Saving data and shutting down...');
  saveData();
  client.destroy();
  process.exit(0);
});

// Validate environment variables
if (!process.env.TOKEN) {
  console.error('❌ ERROR: TOKEN environment variable is required!');
  process.exit(1);
}

client.login(process.env.TOKEN);