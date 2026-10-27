// forwards raw mono microphone samples from the Web Audio rendering thread.
// ref: Hongchan Choi, "AudioWorklet: The Future of Web Audio", ICMC 2018.
// https://quod.lib.umich.edu/i/icmc/bbp2372.2018.021/1
// ref: https://www.w3.org/TR/webaudio-1.1/#AudioWorklet
// ref: https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletProcessor/process
class VoiceCaptureProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const channel = inputs[0]?.[0];
        if (channel?.length) this.port.postMessage(channel.slice());
        return true;
    }
}

registerProcessor('voice-capture', VoiceCaptureProcessor);
