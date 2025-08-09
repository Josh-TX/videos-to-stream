
import { useState, useEffect } from "react";
import usePresetStore from "./PresetStore.jsx"
import Logo from "./Logo.jsx";

const RelevantSettings = ({ settings }) => {
  const keys = Object.keys(settings || {});

  if (keys.length === 0) {
    return <p className="text-muted">Preset has no algorithm settings</p>;
  }

  return (
    <>
        <p>Algorithm Settings:</p>
        <ul style={{marginTop: "0"}}>
        {keys.map((key) => (
            <li key={key} style={{marginTop: "4px"}}>
                <small className="text-muted">{key}</small>: {String(settings[key])}
            </li>
        ))}
        </ul>
    </>
  );
};


const FileBrowser = () => {
    const [filess, setFiless] = useState(null);
    const [showExcluded, setShowExcluded] = useState(true);
    const { getActivePreset, getActiveAlgoPreset } = usePresetStore();
    useEffect(() => {
        const baseUrl = ""
        fetch(baseUrl + '/files')
            .then(res => res.json())
            .then(setFiless);
    }, []);
    if (filess === null) return (
        <>
            <Logo></Logo>
            <p>Loading...</p>
        </>
    );
    const suppressed = filess[0].map(z => ({ cat: "s", path: z }));
    const neutral = filess[1].map(z => ({ cat: "n", path: z }));
    const boosted = filess[2].map(z => ({ cat: "b", path: z }));
    const excluded = filess[3].map(z => ({ cat: "e", path: z }));

    const fileCount = suppressed.length + neutral.length + boosted.length + excluded.length;
    var files = suppressed.concat(neutral).concat(boosted).concat(showExcluded ? excluded : []);
    files.sort((a, b) => a.path.localeCompare(b.path));

    const preset = getActivePreset();
    const presetAlgo = getActiveAlgoPreset();
    const bFactor = parseFloat(preset.BOOSTED_FACTOR)
    const sFactor = parseFloat(preset.SUPPRESSED_FACTOR)
    const sumWeight = suppressed.length + (neutral.length * sFactor) + (boosted.length * sFactor * bFactor);
    const getFileIcon = (cat) => {
        switch (cat) {
            case 's':
                return <span className="icon yellow">↓</span>;
            case 'b':
                return <span className="icon green">↑</span>;
            case 'e':
            return <span className="icon red">✕</span>;
            default:
                return <span className="icon text-muted">-</span>;
        }
    };
    const roundChance = (odds) => {
        if (odds < 4){
            return Math.round(odds * 10) / 10
        } else {
            return Math.round(odds);
        }
    }

    return (
        <>
            <Logo></Logo>
            <div className="center-container" style={{marginTop: 0, padding: "0 4px 8px 4px"}}>
                <p style={{marginBottom: "4px"}}><span className="text-muted">Current Preset:</span> {preset.name}</p>
                <RelevantSettings settings={presetAlgo}></RelevantSettings>
                <h2>Summary</h2>
                <table style={{width: "100%", textAlign: "left",  marginBottom: "16px"}}>
                    <thead>
                        <tr>
                            <th>icon</th>
                            <th>category</th>
                            <th>file count</th>
                            <th>each file's chance</th>
                            <th>sum category %</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><span className="icon green">↑</span></td>
                            <td>boosted</td>
                            <td>{boosted.length}</td>
                            <td>1 in {roundChance(sumWeight / (bFactor * sFactor))}</td>
                            <td>{Math.round(boosted.length * bFactor * sFactor / sumWeight * 1000) / 10}%</td>
                        </tr>
                        <tr>
                            <td><span className="icon text-muted">-</span></td>
                            <td>neutral</td>
                            <td>{neutral.length}</td>
                            <td>1 in {roundChance(sumWeight / sFactor)}</td>
                            <td>{Math.round(neutral.length * sFactor / sumWeight * 1000) / 10}%</td>
                        </tr>
                        <tr>
                            <td><span className="icon yellow">↓</span></td>
                            <td>suppressed</td>
                            <td>{suppressed.length}</td>
                            <td>1 in {sumWeight}</td>
                            <td>{Math.round(suppressed.length / sumWeight * 1000) / 10}%</td>
                        </tr>
                        <tr>
                            <td><span className="icon red">✕</span></td>
                            <td>excluded</td>
                            <td>{excluded.length}</td>
                            <td>none</td>
                            <td>0%</td>
                        </tr>
                    </tbody>
                </table>
                <h2 style={{ marginTop: "20px", marginBottom: "8px" }}>File List</h2>
                <div style={{display: "flex", justifyContent: "space-between", marginBottom: "12px"}} className="text-muted">
                    <span>showing {files.length} of {fileCount}</span>
                    <label>
                        <input
                            type="checkbox"
                            checked={showExcluded}
                            onChange={e => setShowExcluded(e.target.checked)}
                        />
                        Show Excluded Files
                    </label>
                </div>
                {files.map((file) => (
                    <div key={file.path} style={{display: "flex", alignItems: "center", margin: "10px 0"}}>
                        {getFileIcon(file.cat)}
                        <span className="file-path">
                            {file.path}
                        </span>
                    </div>
                ))}
            </div>
        </>
    );
};

export default FileBrowser;
