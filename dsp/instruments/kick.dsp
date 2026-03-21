import("stdfaust.lib");

// OSC-controllable parameters
freq = hslider("freq[osc:/kick/freq]", 60, 20, 200, 1);
decay = hslider("decay[osc:/kick/decay]", 0.3, 0.1, 2, 0.01);
trigger = button("trigger[osc:/kick/trigger]");

// Envelope generator
envelope = trigger : en.ar(0.001, decay);

// Pitch envelope (kick drum characteristic pitch drop)
pitch_env = envelope * 10 + 1;

// Sine oscillator with pitch envelope
osc = os.osc(freq * pitch_env);

// Apply envelope to oscillator
kick = osc * envelope;

// Output with volume control to prevent clipping
process = kick * 0.5;
