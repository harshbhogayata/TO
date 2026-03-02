
const TapeBar = ({ title = "TalentOrbit Auth Portal v2.1", status = "Security: Encrypted", info = "Access Point: Node_01" }) => {
    return (
        <div className="tape-bar" role="banner" aria-hidden="true">
            <span>// {title}</span>
            <span>// {status}</span>
            <span>// {info}</span>
        </div>
    );
};

export default TapeBar;
