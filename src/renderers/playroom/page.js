(() => {
  const config = JSON.parse(document.getElementById("playroom-config").textContent);
  const form = document.getElementById("playroom-form");
  const languageSelect = document.getElementById("language");
  const voiceSelect = document.getElementById("voice");
  const statusNode = document.getElementById("status");
  const submitButton = document.getElementById("submit-button");
  const historyBody = document.getElementById("history-body");
  const fields = {
    speakerId: document.getElementById("speaker_id"),
    sentenceSilence: document.getElementById("sentence_silence"),
    lengthScale: document.getElementById("length_scale"),
    noiseScale: document.getElementById("noise_scale"),
    noiseWScale: document.getElementById("noise_w_scale"),
    volume: document.getElementById("volume"),
    normalizeAudio: document.getElementById("normalize_audio"),
    includeAlignments: document.getElementById("include_alignments"),
    showTimestamps: document.getElementById("show_timestamps"),
    grammar: document.getElementById("grammar"),
    text: document.getElementById("text")
  };

  const state = {
    groups: []
  };

  function setStatus(message, tone) {
    statusNode.textContent = message || "";
    statusNode.dataset.tone = tone || "";
  }

  function setDefaults() {
    fields.speakerId.value = config.defaults.speaker_id ?? "";
    fields.sentenceSilence.value = config.defaults.sentence_silence;
    fields.lengthScale.value = config.defaults.length_scale;
    fields.noiseScale.value = config.defaults.noise_scale;
    fields.noiseWScale.value = config.defaults.noise_w_scale;
    fields.volume.value = config.defaults.volume;
    fields.normalizeAudio.checked = Boolean(config.defaults.normalize_audio);
    fields.includeAlignments.checked = Boolean(config.defaults.include_alignments);
    fields.grammar.value = "";
  }

  function parseGrammarInput(rawValue) {
    const lines = rawValue
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    return lines.length > 0 ? lines : null;
  }

  function base64ToWavBlob(base64Data) {
    const binary = atob(base64Data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: "audio/wav" });
  }

  function inferLanguageCode(voiceId) {
    const match = voiceId.match(/^([a-z]{2}_[A-Z]{2})-/);
    return match ? match[1] : "unknown";
  }

  function normalizeLanguage(voiceId, meta) {
    const language = meta && typeof meta.language === "object" ? meta.language : {};
    const code =
      (typeof meta.language === "string" && meta.language) ||
      language.code ||
      language.id ||
      language.tag ||
      language.iso_code ||
      inferLanguageCode(voiceId);
    const label =
      language.name_english ||
      language.english_name ||
      language.name ||
      language.native_name ||
      code;

    return { code, label };
  }

  function normalizeVoiceMeta(voiceId, meta) {
    const language = normalizeLanguage(voiceId, meta || {});
    const quality = meta && (meta.quality || meta.voice_quality);
    const baseName =
      meta && (meta.name || meta.voice_name) ? (meta.name || meta.voice_name) : voiceId;
    const label = quality ? `${baseName} (${quality})` : baseName;

    return {
      id: voiceId,
      label,
      languageCode: language.code,
      languageLabel: language.label
    };
  }

  function buildGroups(voicesPayload) {
    const groupsMap = new Map();

    Object.entries(voicesPayload || {}).forEach(([voiceId, meta]) => {
      const voice = normalizeVoiceMeta(voiceId, meta);
      if (!groupsMap.has(voice.languageCode)) {
        groupsMap.set(voice.languageCode, {
          code: voice.languageCode,
          label: voice.languageLabel,
          voices: []
        });
      }
      groupsMap.get(voice.languageCode).voices.push(voice);
    });

    return Array.from(groupsMap.values())
      .map((group) => ({
        code: group.code,
        label: group.label,
        voices: group.voices.sort((a, b) => a.label.localeCompare(b.label))
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }

  function replaceOptions(selectNode, options, selectedValue) {
    selectNode.innerHTML = "";
    options.forEach((optionData) => {
      const option = document.createElement("option");
      option.value = optionData.value;
      option.textContent = optionData.label;
      if (selectedValue && optionData.value === selectedValue) {
        option.selected = true;
      }
      selectNode.appendChild(option);
    });
  }

  function populateLanguages(selectedLanguageCode) {
    const languageOptions = state.groups.map((group) => ({
      value: group.code,
      label: group.label
    }));
    const nextSelectedLanguage =
      selectedLanguageCode && state.groups.some((group) => group.code === selectedLanguageCode)
        ? selectedLanguageCode
        : state.groups[0] && state.groups[0].code;

    replaceOptions(languageSelect, languageOptions, nextSelectedLanguage);
    languageSelect.disabled = state.groups.length === 0;
  }

  function populateVoices(selectedVoiceId) {
    const activeLanguageCode = languageSelect.value;
    const activeGroup = state.groups.find((group) => group.code === activeLanguageCode);
    const voices = activeGroup ? activeGroup.voices : [];
    const nextSelectedVoice =
      selectedVoiceId && voices.some((voice) => voice.id === selectedVoiceId)
        ? selectedVoiceId
        : voices[0] && voices[0].id;

    replaceOptions(
      voiceSelect,
      voices.map((voice) => ({ value: voice.id, label: voice.label })),
      nextSelectedVoice
    );
    voiceSelect.disabled = voices.length === 0;
  }

  async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Request failed for ${url} (${response.status})`);
    }
    return response.json();
  }

  async function loadVoices() {
    let voicesPayload;
    try {
      voicesPayload = await fetchJson("/all-voices");
    } catch (error) {
      setStatus("Failed to load /all-voices, falling back to /voices.", "warning");
      voicesPayload = await fetchJson("/voices");
    }

    state.groups = buildGroups(voicesPayload);
    if (state.groups.length === 0) {
      throw new Error("No voices available");
    }

    let initialLanguageCode = null;
    if (config.default_voice) {
      const defaultGroup = state.groups.find((group) =>
        group.voices.some((voice) => voice.id === config.default_voice)
      );
      initialLanguageCode = defaultGroup ? defaultGroup.code : null;
    }

    populateLanguages(initialLanguageCode);
    populateVoices(config.default_voice);

    languageSelect.disabled = false;
    voiceSelect.disabled = false;
    submitButton.disabled = false;
    setStatus(`Loaded ${state.groups.length} language groups.`, "success");
  }

  function numericValue(inputNode, options) {
    const rawValue = inputNode.value.trim();
    if (rawValue === "") {
      return options.allowBlank ? null : options.defaultValue;
    }

    const parsed = Number(rawValue);
    if (Number.isNaN(parsed)) {
      throw new Error(`${options.label} must be a number`);
    }

    return parsed;
  }

  function renderSeekableWords(textCell, audioNode, wordAlignments) {
    const listNode = document.createElement("div");
    listNode.className = "word-list";

    const seekAndPlay = (startSeconds) => {
      const playFrom = Number.isFinite(startSeconds) && startSeconds >= 0 ? startSeconds : 0;
      const applySeek = () => {
        audioNode.currentTime = Math.max(0, playFrom);
        audioNode.play().catch(() => {
          // Ignore autoplay restrictions; user can press play manually.
        });
      };

      if (audioNode.readyState >= 1) {
        applySeek();
      } else {
        audioNode.addEventListener("loadedmetadata", applySeek, { once: true });
      }
    };

    wordAlignments.forEach((wordData) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "word-chip";
      chip.dataset.start = String(wordData.start);

      const wordText = document.createTextNode(String(wordData.word || ""));
      chip.appendChild(wordText);

      const badge = document.createElement("span");
      badge.className = "word-chip-time";
      badge.textContent = "(" + Number(wordData.start).toFixed(2) + "s)";
      chip.appendChild(badge);

      chip.addEventListener("click", () => {
        seekAndPlay(Number(chip.dataset.start));
      });

      listNode.appendChild(chip);
    });

    if (fields.showTimestamps.checked) {
      listNode.classList.add("show-timestamps");
    }

    textCell.appendChild(listNode);
  }

  function addHistoryRow(payload, audioBlob, wordAlignments) {
    const emptyRow = historyBody.querySelector(".empty-state-row");
    if (emptyRow) {
      emptyRow.remove();
    }

    const audioUrl = URL.createObjectURL(audioBlob);
    const activeGroup = state.groups.find((group) => group.code === languageSelect.value);
    const activeVoice =
      activeGroup && activeGroup.voices.find((voice) => voice.id === payload.voice);
    const row = document.createElement("tr");
    const createdCell = document.createElement("td");
    const languageCell = document.createElement("td");
    const voiceCell = document.createElement("td");
    const textCell = document.createElement("td");
    const audioCell = document.createElement("td");
    const audioNode = document.createElement("audio");

    createdCell.textContent = new Date().toLocaleTimeString();
    languageCell.textContent = activeGroup ? activeGroup.label : languageSelect.value;
    voiceCell.textContent = activeVoice ? activeVoice.label : payload.voice;
    textCell.className = "text-cell";
    if (Array.isArray(wordAlignments) && wordAlignments.length > 0) {
      renderSeekableWords(textCell, audioNode, wordAlignments);
    } else {
      textCell.textContent = payload.text;
    }
    audioNode.controls = true;
    audioNode.src = audioUrl;
    audioCell.appendChild(audioNode);

    row.appendChild(createdCell);
    row.appendChild(languageCell);
    row.appendChild(voiceCell);
    row.appendChild(textCell);
    row.appendChild(audioCell);
    historyBody.prepend(row);
  }

  fields.showTimestamps.addEventListener("change", () => {
    historyBody.querySelectorAll(".word-list").forEach((list) => {
      list.classList.toggle("show-timestamps", fields.showTimestamps.checked);
    });
  });

  languageSelect.addEventListener("change", () => {
    populateVoices();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitButton.disabled = true;
    setStatus("Generating audio...", "");

    try {
      const text = fields.text.value.trim();
      if (!text) {
        throw new Error("Text is required");
      }

      const payload = {
        voice: voiceSelect.value,
        text,
        include_alignments: fields.includeAlignments.checked,
        sentence_silence: numericValue(fields.sentenceSilence, {
          label: "sentence_silence",
          defaultValue: config.defaults.sentence_silence,
          allowBlank: false
        }),
        length_scale: numericValue(fields.lengthScale, {
          label: "length_scale",
          defaultValue: config.defaults.length_scale,
          allowBlank: false
        }),
        noise_scale: numericValue(fields.noiseScale, {
          label: "noise_scale",
          defaultValue: config.defaults.noise_scale,
          allowBlank: false
        }),
        noise_w_scale: numericValue(fields.noiseWScale, {
          label: "noise_w_scale",
          defaultValue: config.defaults.noise_w_scale,
          allowBlank: false
        }),
        volume: numericValue(fields.volume, {
          label: "volume",
          defaultValue: config.defaults.volume,
          allowBlank: false
        }),
        normalize_audio: fields.normalizeAudio.checked
      };

      const grammar = parseGrammarInput(fields.grammar.value);
      if (grammar) {
        payload.grammar = grammar;
      }

      const speakerId = numericValue(fields.speakerId, {
        label: "speaker_id",
        defaultValue: null,
        allowBlank: true
      });
      if (speakerId !== null) {
        payload.speaker_id = speakerId;
      }

      const response = await fetch("/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        let errorMessage = `Synthesis failed (${response.status})`;
        try {
          const errorPayload = await response.json();
          if (errorPayload && errorPayload.error) {
            errorMessage = errorPayload.error;
          }
        } catch (error) {
          // Keep the HTTP status-based error.
        }
        throw new Error(errorMessage);
      }

      let audioBlob;
      let wordAlignments = null;
      if (payload.include_alignments) {
        const alignedPayload = await response.json();
        if (!alignedPayload || !alignedPayload.audio_base64) {
          throw new Error("Missing audio_base64 in alignment response");
        }

        audioBlob = base64ToWavBlob(alignedPayload.audio_base64);
        if (alignedPayload.alignments && Array.isArray(alignedPayload.alignments.words)) {
          wordAlignments = alignedPayload.alignments.words;
        }

        if (alignedPayload.alignment_supported === false && alignedPayload.alignment_error) {
          setStatus(`Audio generated (alignment warning: ${alignedPayload.alignment_error})`, "warning");
        }
      } else {
        audioBlob = await response.blob();
      }

      addHistoryRow(payload, audioBlob, wordAlignments);
      if (!(payload.include_alignments && statusNode.dataset.tone === "warning")) {
        setStatus("Audio generated.", "success");
      }
    } catch (error) {
      setStatus(error.message || "Failed to generate audio.", "error");
    } finally {
      submitButton.disabled = false;
    }
  });

  setDefaults();
  loadVoices().catch((error) => {
    setStatus(error.message || "Failed to load voices.", "error");
  });
})();
